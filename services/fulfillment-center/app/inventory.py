from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .audit import write_audit
from .config import get_settings
from .db import connect
from .inventory_formats import (
    AccountFormatError,
    InventoryExportError,
    build_inventory_export,
    parse_account_json,
    parse_account_payload,
)
from .settings_store import get_setting


BAD_LIFECYCLE = {"invalid", "expired", "revoked", "disabled", "used", "consumed"}
BAD_DISPLAY = {"invalid", "expired", "revoked", "disabled"}
BAD_VALIDITY = {"invalid", "expired", "revoked", "disabled"}
VALIDITY_VALUES = BAD_VALIDITY | {"valid", "unknown", "registered", "not_available"}
DISPLAY_VALUES = BAD_DISPLAY | {"valid", "unknown", "registered", "not_available"}
PLATFORM_ALIASES = {
    "chatgpt": "chatgpt",
    "openai": "chatgpt",
    "codex": "chatgpt",
    "openai-codex": "chatgpt",
    "openai_codex": "chatgpt",
    "openai codex": "chatgpt",
}


class InventoryDeleteBlocked(RuntimeError):
    pass


def _pick(data: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def _pick_sources(
    sources: list[dict[str, Any]], *keys: str, default: Any = ""
) -> Any:
    for source in sources:
        value = _pick(source, *keys, default=None)
        if value not in (None, ""):
            return value
    return default


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return _text(value).lower() in {"1", "true", "yes", "on", "y", "revoked"}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _normalize_platform(value: Any) -> str:
    """Normalize only known CPA platform aliases; keep unknown values visible."""
    platform = _text(value)
    return PLATFORM_ALIASES.get(platform.lower(), platform)


def _platform_values(value: Any) -> list[str]:
    """Return stored spellings that belong to one known canonical platform."""
    canonical = _normalize_platform(value) or "chatgpt"
    values = [alias for alias, target in PLATFORM_ALIASES.items() if target == canonical]
    return values or [canonical]


def _json_values_from_text(text: str) -> list[Any]:
    """Extract one or more JSON values from pasted text or fenced markdown."""
    value = str(text or "").strip()
    if not value:
        return []
    value = value.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    try:
        return [json.loads(value)]
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    values: list[Any] = []
    index = 0
    while index < len(value):
        starts = [value.find(marker, index) for marker in ("{", "[")]
        starts = [position for position in starts if position >= 0]
        if not starts:
            break
        start = min(starts)
        try:
            parsed, end = decoder.raw_decode(value[start:])
        except json.JSONDecodeError:
            index = start + 1
            continue
        values.append(parsed)
        index = start + max(1, end)
    return values


def _items_from_cpa(payload: Any) -> list[dict[str, Any]]:
    return parse_account_json(payload)


def _credentials_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        result: dict[str, Any] = {}
        direct_keys = (
            "access_token", "accessToken", "refresh_token", "refreshToken",
            "id_token", "idToken", "session_token", "sessionToken",
            "account_id", "accountId", "chatgpt_account_id", "cookies", "cookie",
            "email", "password", "pwd", "expires_at", "expiresAt", "expired",
            "exp", "token_revoked", "revoked", "is_revoked",
        )
        for entry in value:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key") or entry.get("name")
            if key and entry.get("value") not in (None, ""):
                result[str(key)] = entry.get("value")
            for direct in direct_keys:
                if entry.get(direct) not in (None, ""):
                    result[direct] = entry.get(direct)
        return result
    return {}


def _source_maps(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Return common CPA containers in precedence order."""
    sources: list[dict[str, Any]] = [raw]
    for key in ("credentials", "tokens", "oauth", "auth", "agent_identity"):
        value = raw.get(key)
        if isinstance(value, dict):
            sources.append(value)
        elif isinstance(value, list):
            sources.append(_credentials_dict(value))
    for key in ("overview", "https://api.openai.com/auth", "https://api.openai.com/profile"):
        value = raw.get(key)
        if isinstance(value, dict):
            sources.append(value)
    return sources


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode untrusted JWT payload metadata; never verifies a signature."""
    try:
        candidate = _text(token)
        if candidate.lower().startswith("bearer "):
            candidate = candidate[7:].strip()
        parts = candidate.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        data = json.loads(
            base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
        )
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _claim_maps(claims: dict[str, Any]) -> list[dict[str, Any]]:
    maps: list[dict[str, Any]] = [claims]
    for key in (
        "https://api.openai.com/auth",
        "https://api.openai.com/profile",
        "auth",
        "profile",
        "user",
    ):
        value = claims.get(key)
        if isinstance(value, dict):
            maps.append(value)
    return maps


def _parse_expiry(value: Any) -> datetime | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 100_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = _text(value)
    if text.isdigit():
        return _parse_expiry(int(text))
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_expiry(value: Any) -> str:
    if isinstance(value, bool):
        return ""
    parsed = _parse_expiry(value)
    return parsed.isoformat() if parsed else _text(value)


def _expiry_state(value: Any) -> str:
    if value in (None, ""):
        return "unknown"
    if isinstance(value, bool):
        return "expired" if value else "unknown"
    parsed = _parse_expiry(value)
    if parsed is None:
        return "invalid"
    return "expired" if parsed <= datetime.now(timezone.utc) else "valid"


def _claim_value(claims: dict[str, Any], *keys: str) -> Any:
    for source in _claim_maps(claims):
        value = _pick(source, *keys, default=None)
        if value not in (None, ""):
            return value
    return ""


def _token_metadata(access_token: str, id_token: str) -> dict[str, Any]:
    account_id = ""
    email = ""
    expiry_values: list[Any] = []
    revoked = False
    claims_present = False
    claim_status = ""
    expired_flags: list[Any] = []
    for token in (access_token, id_token):
        claims = _decode_jwt_payload(token)
        if not claims:
            continue
        claims_present = True
        account_id = account_id or _text(
            _claim_value(claims, "chatgpt_account_id", "account_id", "accountId")
        )
        email = email or _text(
            _claim_value(claims, "email", "preferred_username", "upn", "username")
        )
        for source in _claim_maps(claims):
            for key in ("exp", "expires_at", "expiresAt"):
                value = source.get(key)
                if value not in (None, ""):
                    expiry_values.append(value)
            if source.get("expired") not in (None, ""):
                expired_flags.append(source.get("expired"))
            if any(
                _as_bool(source.get(key))
                for key in ("token_revoked", "revoked", "is_revoked")
            ):
                revoked = True
            status = _text(source.get("status") or source.get("lifecycle_status")).lower()
            if status in BAD_LIFECYCLE:
                claim_status = status
                revoked = revoked or status == "revoked"

    parsed_expiries = [
        parsed
        for value in expiry_values
        if (parsed := _parse_expiry(value)) is not None
    ]
    expires_at = ""
    if parsed_expiries:
        expires_at = min(parsed_expiries).isoformat()
    elif expiry_values:
        expires_at = _canonical_expiry(expiry_values[0])
    expiry_state = _expiry_state(expires_at)
    if any(_as_bool(value) for value in expired_flags):
        expiry_state = "expired"
    return {
        "account_id": account_id,
        "email": email,
        "expires_at": expires_at,
        "expiry_state": expiry_state,
        "token_revoked": revoked,
        "claim_status": claim_status,
        "expired_claim": any(_as_bool(value) for value in expired_flags),
        "claims_present": claims_present,
    }


def extract_oauth_fields(item: dict[str, Any]) -> dict[str, Any]:
    """Resolve normalized OAuth fields and untrusted token metadata."""
    raw = item
    source_payload = item.get("source_payload")
    if source_payload:
        try:
            decoded = json.loads(str(source_payload))
            if isinstance(decoded, dict):
                raw = decoded
        except (TypeError, ValueError, json.JSONDecodeError):
            raw = {}
    sources = _source_maps(raw)
    access_token = _text(
        item.get("primary_token")
        or _pick_sources(sources, "primary_token", "primaryToken", "token", "access_token", "accessToken")
    )
    refresh_token = _text(
        item.get("refresh_token")
        or _pick_sources(sources, "refresh_token", "refreshToken")
    )
    id_token = _text(
        item.get("id_token")
        or _pick_sources(sources, "id_token", "idToken")
    )
    metadata = _token_metadata(access_token, id_token)
    account_id = _text(
        item.get("account_id")
        or _pick_sources(sources, "chatgpt_account_id", "account_id", "accountId")
        or metadata["account_id"]
    )
    email = _text(
        item.get("email")
        or _pick_sources(sources, "email", "account", "username", "name")
        or metadata["email"]
    )
    explicit_expiry = _pick(item, "expires_at", "expiresAt", default=None)
    if explicit_expiry in (None, ""):
        explicit_expiry = _pick_sources(
            sources, "expires_at", "expiresAt", default=None
        )
    if explicit_expiry in (None, ""):
        expired_marker = _pick(item, "expired", default=None)
        if expired_marker in (None, ""):
            expired_marker = _pick_sources(sources, "expired", default=None)
        if _as_bool(expired_marker):
            explicit_expiry = True
    expires_at = _canonical_expiry(
        metadata["expires_at"] if explicit_expiry in (None, "") else explicit_expiry
    )
    expiry_state = _expiry_state(expires_at)
    if metadata["expiry_state"] == "expired":
        expiry_state = "expired"
    if metadata["expired_claim"]:
        expiry_state = "expired"
    token_revoked = _as_bool(
        item.get("token_revoked")
        or _pick_sources(sources, "token_revoked", "revoked", "is_revoked")
    ) or metadata["token_revoked"]
    if _text(
        _pick_sources(sources, "lifecycle_status", "status")
    ).lower() == "revoked":
        token_revoked = True
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "id_token": id_token,
        "account_id": account_id,
        "email": email.lower() if "@" in email else email,
        "expires_at": expires_at,
        "expiry_state": expiry_state,
        "token_revoked": token_revoked,
        "claims_present": metadata["claims_present"],
        "claim_status": metadata["claim_status"],
        "expired_claim": metadata["expired_claim"],
    }


def normalize_account(raw: dict[str, Any]) -> dict[str, Any]:
    sources = _source_maps(raw)
    oauth = extract_oauth_fields(raw)
    raw_status = _text(_pick_sources(sources, "status"))
    explicit_lifecycle = _text(_pick_sources(sources, "lifecycle_status"))
    claim_status = _text(oauth["claim_status"]).lower()
    lifecycle_status = explicit_lifecycle or (
        claim_status
        if claim_status in BAD_LIFECYCLE
        else raw_status if raw_status.lower() in BAD_LIFECYCLE else "registered"
    )
    explicit_validity = _text(
        _pick_sources(sources, "validity_status", "validity")
    ).lower()
    if not explicit_validity and raw_status.lower() in VALIDITY_VALUES:
        explicit_validity = raw_status.lower()
    if oauth["token_revoked"]:
        validity_status = "revoked"
    elif oauth["expiry_state"] == "expired" or oauth["claim_status"] == "expired":
        validity_status = "expired"
    elif claim_status in {"invalid", "disabled"}:
        validity_status = claim_status
    elif explicit_validity in BAD_VALIDITY:
        validity_status = explicit_validity
    elif (
        oauth["access_token"]
        and oauth["claims_present"]
        and claim_status not in BAD_LIFECYCLE
        and explicit_validity in {"", "unknown", "not_available"}
        and oauth["expiry_state"] != "invalid"
    ):
        # Claims provide useful metadata only. Provider-side auth still decides
        # whether the token is genuine, current, and accepted for activation.
        validity_status = "valid"
    else:
        validity_status = explicit_validity or "unknown"
    display_status = _text(_pick_sources(sources, "display_status"))
    if not display_status and raw_status.lower() in DISPLAY_VALUES:
        display_status = raw_status
    display_status = display_status or "registered"
    token_revoked = bool(oauth["token_revoked"])
    account_id = oauth["account_id"]
    email = oauth["email"]
    external_seed = _pick(
        raw, "id", "user_id", default=account_id or email or json.dumps(raw, sort_keys=True)
    )
    external_id = hashlib.sha256(str(external_seed).encode("utf-8")).hexdigest()
    platform = _normalize_platform(
        _pick_sources(sources, "platform", default=get_settings().cpa_platform)
        or "chatgpt"
    )
    return {
        "external_id": external_id,
        "platform": platform,
        "email": email,
        "account_id": account_id,
        "password": _text(_pick_sources(sources, "password", "pwd", "account_password")),
        "primary_token": oauth["access_token"],
        "id_token": oauth["id_token"],
        "session_token": _text(_pick_sources(sources, "session_token", "sessionToken")),
        "refresh_token": oauth["refresh_token"],
        "cookies": _text(_pick_sources(sources, "cookies", "cookie")),
        "lifecycle_status": lifecycle_status,
        "validity_status": validity_status,
        "display_status": display_status,
        "token_revoked": 1 if token_revoked else 0,
        "expires_at": oauth["expires_at"],
        "reset_count": _as_int(_pick_sources(sources, "reset_count", "resetCount", "resets", default=0)),
        "source_payload": json.dumps(raw, ensure_ascii=False),
    }


def _import_accounts(payload: Any, *, audit_event: str) -> dict[str, Any]:
    parsed = parse_account_payload(payload)
    items = [normalize_account(item) for item in parsed.accounts]
    created = 0
    updated = 0
    skipped = 0
    details: list[dict[str, Any]] = []

    def add_detail(
        action: str,
        inventory_id: int,
        email: str,
        item: dict[str, Any],
        status: str = "available",
    ) -> None:
        if len(details) < 200:
            preview = {"status": status, **item}
            allocatable, allocation_reason = is_eligible(preview)
            activatable, activation_reason = activation_eligibility(preview)
            details.append(
                {
                    "action": action,
                    "inventory_id": inventory_id,
                    "email": email,
                    "eligible": allocatable,
                    "eligible_reason": allocation_reason,
                    "activation_eligible": activatable,
                    "activation_eligible_reason": activation_reason,
                }
            )

    fields = (
        "external_id", "platform", "email", "account_id", "password",
        "primary_token", "id_token", "session_token", "refresh_token",
        "cookies", "lifecycle_status", "validity_status", "display_status",
        "token_revoked", "expires_at", "reset_count", "source_payload",
    )
    with connect() as conn:
        for item in items:
            lookup_clauses = ["external_id = ?"]
            lookup_params: list[Any] = [item["external_id"]]
            if item["account_id"]:
                lookup_clauses.append("account_id = ?")
                lookup_params.append(item["account_id"])
            if item["email"]:
                lookup_clauses.append("lower(email) = lower(?)")
                lookup_params.append(item["email"])
            row = conn.execute(
                f"""
                SELECT * FROM inventory_items
                WHERE {' OR '.join(lookup_clauses)}
                ORDER BY id ASC LIMIT 1
                """,
                tuple(lookup_params),
            ).fetchone()
            if row is None:
                cursor = conn.execute(
                    """
                    INSERT INTO inventory_items(
                        external_id, platform, email, account_id, password,
                        primary_token, id_token, session_token, refresh_token,
                        cookies, lifecycle_status, validity_status, display_status,
                        token_revoked, expires_at, reset_count, source_payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(item[field] for field in fields),
                )
                created += 1
                add_detail(
                    "created", int(cursor.lastrowid), str(item["email"]), item
                )
                continue

            current = dict(row)
            changed = any(current.get(field) != item[field] for field in fields)
            if not changed:
                skipped += 1
                add_detail(
                    "skipped",
                    int(current["id"]),
                    str(current.get("email") or item["email"]),
                    {**current, **item},
                    status=str(current.get("status") or "available"),
                )
                continue
            conn.execute(
                """
                UPDATE inventory_items
                SET external_id = ?, platform = ?, email = ?, account_id = ?,
                    password = ?, primary_token = ?, id_token = ?,
                    session_token = ?, refresh_token = ?, cookies = ?,
                    lifecycle_status = ?, validity_status = ?, display_status = ?,
                    token_revoked = ?, expires_at = ?, reset_count = ?,
                    source_payload = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (*[item[field] for field in fields], int(current["id"])),
            )
            updated += 1
            add_detail(
                "updated", int(current["id"]), str(item["email"]), item,
                status=str(current.get("status") or "available"),
            )

    result = {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": len(items),
        "ignored": parsed.skipped,
        "formats": list(parsed.detected_formats),
        "details": details,
        "details_truncated": len(items) > len(details),
    }
    write_audit(audit_event, payload=result)
    check_low_stock()
    return result


def import_cpa(payload: Any) -> dict[str, Any]:
    """Backward-compatible CPA entry point backed by the unified parser."""
    return _import_accounts(payload, audit_event="inventory.import_cpa")


def import_json(payload: Any) -> dict[str, Any]:
    return _import_accounts(payload, audit_event="inventory.import_json")


def desktop_oauth_status(row: dict[str, Any]) -> dict[str, Any]:
    oauth = extract_oauth_fields(row)
    fields = {
        "access_token": oauth["access_token"],
        "refresh_token": oauth["refresh_token"],
        "id_token": oauth["id_token"],
        "account_id": oauth["account_id"],
    }
    missing = [name for name, value in fields.items() if not value]
    if oauth["expiry_state"] == "invalid":
        missing.append("invalid_expiry")
    if oauth["token_revoked"]:
        missing.append("revoked")
    return {
        "ready": not missing,
        "missing": missing,
        "account_id": oauth["account_id"],
        "expires_at": oauth["expires_at"],
    }


def _hydrate_inventory_item(row: dict[str, Any]) -> dict[str, Any]:
    """Backfill metadata for rows imported before the claims columns existed."""
    item = dict(row)
    item["platform"] = _normalize_platform(item.get("platform") or "chatgpt") or "chatgpt"
    oauth = extract_oauth_fields(item)
    for key in ("email", "account_id", "expires_at"):
        if not item.get(key) and oauth[key]:
            item[key] = oauth[key]
    if not item.get("id_token") and oauth["id_token"]:
        item["id_token"] = oauth["id_token"]
    validity = _text(item.get("validity_status")).lower()
    if validity in {"", "unknown", "not_available"} and oauth["token_revoked"]:
        item["validity_status"] = "revoked"
    if oauth["token_revoked"]:
        item["token_revoked"] = 1
    claim_status = _text(oauth["claim_status"]).lower()
    if validity in {"", "unknown", "not_available"}:
        if oauth["expiry_state"] == "expired":
            item["validity_status"] = "expired"
        elif claim_status in {"invalid", "disabled"}:
            item["validity_status"] = claim_status
        elif (
            oauth["access_token"]
            and oauth["claims_present"]
            and claim_status not in BAD_LIFECYCLE
            and oauth["expiry_state"] != "invalid"
            and not oauth["token_revoked"]
        ):
            item["validity_status"] = "valid"
    lifecycle = _text(item.get("lifecycle_status")).lower()
    if lifecycle in {"", "registered"} and claim_status in {"used", "consumed"}:
        item["lifecycle_status"] = claim_status
    return item


def activation_eligibility(row: dict[str, Any]) -> tuple[bool, str]:
    """Check activation prerequisites; the provider determines token expiration."""
    settings = get_settings()
    item = _hydrate_inventory_item(row)
    oauth = extract_oauth_fields(item)
    validity = _text(item.get("validity_status")).lower()
    lifecycle = _text(item.get("lifecycle_status")).lower()
    display = _text(item.get("display_status")).lower()
    if oauth["expiry_state"] == "invalid":
        return False, "invalid_token_expiry"
    if (
        oauth["token_revoked"]
        or oauth["claim_status"] == "revoked"
        or validity == "revoked"
        or lifecycle == "revoked"
    ):
        return False, "token_revoked"
    if validity in {"invalid", "disabled"}:
        return False, "invalid_validity"
    if lifecycle in BAD_LIFECYCLE - {"expired"} or oauth["claim_status"] in {"used", "consumed"}:
        return False, "bad_lifecycle"
    if oauth["claim_status"] in {"invalid", "disabled"}:
        return False, "invalid_validity"
    if display in BAD_DISPLAY - {"expired"}:
        return False, "bad_display"
    if _as_int(item.get("reset_count")) > settings.max_reset_count:
        return False, "reset_count_exceeded"

    email = _text(item.get("email") or oauth["email"])
    if "@" not in email:
        return False, "missing_email"

    access_token = oauth["access_token"]
    if access_token:
        if not oauth["account_id"]:
            return False, "missing_account_id"
        provider = get_setting(
            "activation_provider", settings.activation_provider
        ).strip().lower() or settings.activation_provider
        if not settings.dry_run and provider == "desktop":
            oauth_status = desktop_oauth_status(item)
            if not oauth_status["ready"]:
                return False, "missing_desktop_oauth:" + ",".join(oauth_status["missing"])
        if not settings.dry_run and provider == "cli" and not oauth["refresh_token"]:
            return False, "missing_cli_oauth:refresh_token"
        return True, "ok"

    has_legacy_credentials = bool(
        _text(item.get("password"))
        or _text(item.get("session_token"))
        or _text(item.get("cookies"))
    )
    if not has_legacy_credentials:
        return False, "missing_credentials"
    if not settings.dry_run:
        return False, "missing_access_token"
    return True, "ok"


def is_eligible(row: dict[str, Any]) -> tuple[bool, str]:
    if _text(row.get("status")) != "available":
        return False, "not_available"
    item = _hydrate_inventory_item(row)
    oauth = extract_oauth_fields(item)
    if (
        oauth["expiry_state"] == "expired"
        or oauth["expired_claim"]
        or oauth["claim_status"] == "expired"
        or _text(item.get("validity_status")).lower() == "expired"
        or _text(item.get("lifecycle_status")).lower() == "expired"
    ):
        return False, "token_expired"
    if _text(item.get("display_status")).lower() == "expired":
        return False, "bad_display"
    return activation_eligibility(row)


def reserve_many(order_id: str, quantity: int, platform: str = "chatgpt") -> list[dict[str, Any]]:
    platform_values = _platform_values(platform)
    quantity = max(1, int(quantity or 1))
    reserved: list[dict[str, Any]] = []
    skipped_reasons: set[str] = set()
    with connect() as conn:
        # Serialize stock allocation. A deferred transaction can let two
        # concurrent requests read the same available row before either
        # UPDATE runs; only count rows whose conditional UPDATE succeeded.
        conn.execute("BEGIN IMMEDIATE")
        placeholders = ", ".join("?" for _ in platform_values)
        rows = conn.execute(
            f"""
            SELECT * FROM inventory_items
            WHERE platform IN ({placeholders}) AND status = 'available'
            ORDER BY id ASC
            """,
            tuple(platform_values),
        ).fetchall()
        for row in rows:
            data = _hydrate_inventory_item(dict(row))
            ok, reason = is_eligible(data)
            if not ok:
                skipped_reasons.add(reason)
                continue
            updated = conn.execute(
                """
                UPDATE inventory_items
                SET status = 'shipped', reserved_order_id = ?, shipped_at = datetime('now'), updated_at = datetime('now')
                WHERE id = ? AND status = 'available'
                """,
                (order_id, data["id"]),
            )
            if updated.rowcount:
                reserved.append(data)
            if len(reserved) >= quantity:
                break
        if len(reserved) < quantity:
            suffix = (
                "；不可出库原因：" + ",".join(sorted(skipped_reasons))
                if skipped_reasons
                else ""
            )
            raise RuntimeError(
                f"合格库存不足：需要 {quantity} 个，当前只能出库 {len(reserved)} 个{suffix}"
            )
    for item in reserved:
        write_audit("inventory.shipped", order_id=order_id, inventory_id=item["id"])
    check_low_stock()
    return reserved



def reserve_missing_for_order(
    order_id: str,
    target_quantity: int,
    platform: str = "chatgpt",
) -> list[dict[str, Any]]:
    """Reserve only the missing portion of an already partially shipped order."""
    platform_values = _platform_values(platform)
    target_quantity = max(1, int(target_quantity or 1))
    reserved: list[dict[str, Any]] = []
    skipped_reasons: set[str] = set()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = int(conn.execute(
            "SELECT COUNT(*) AS n FROM fulfillment_items WHERE order_id = ?",
            (order_id,),
        ).fetchone()["n"] or 0)
        needed = max(0, target_quantity - current)
        if not needed:
            return []
        placeholders = ", ".join("?" for _ in platform_values)
        rows = conn.execute(
            f"""
            SELECT * FROM inventory_items
            WHERE platform IN ({placeholders}) AND status = 'available'
            ORDER BY id ASC
            """,
            tuple(platform_values),
        ).fetchall()
        for row in rows:
            data = _hydrate_inventory_item(dict(row))
            ok, reason = is_eligible(data)
            if not ok:
                skipped_reasons.add(reason)
                continue
            updated = conn.execute(
                """
                UPDATE inventory_items
                SET status = 'shipped', reserved_order_id = ?, shipped_at = datetime('now'), updated_at = datetime('now')
                WHERE id = ? AND status = 'available'
                """,
                (order_id, data["id"]),
            )
            if updated.rowcount:
                reserved.append(data)
            if len(reserved) >= needed:
                break
        if len(reserved) < needed:
            suffix = (
                "；不可出库原因：" + ",".join(sorted(skipped_reasons))
                if skipped_reasons
                else ""
            )
            raise RuntimeError(
                f"合格库存不足：订单需要补发 {needed} 个，当前只能补发 {len(reserved)} 个{suffix}"
            )
    for item in reserved:
        write_audit("inventory.shipped_top_up", order_id=order_id, inventory_id=item["id"])
    check_low_stock()
    return reserved

def mark_activation_started(inventory_id: int, order_id: str, job_id: str = "") -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE inventory_items
            SET status = 'activating', activation_error = '', updated_at = datetime('now')
            WHERE id = ?
            """,
            (inventory_id,),
        )
        conn.execute(
            """
            UPDATE fulfillment_items
            SET status = 'activating', activation_error = '', updated_at = datetime('now')
            WHERE order_id = ? AND inventory_id = ?
            """,
            (order_id, inventory_id),
        )
    write_audit("inventory.activation_started", order_id=order_id, inventory_id=inventory_id, payload={"job_id": job_id})


def mark_activated(inventory_id: int, order_id: str, reply: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE inventory_items
            SET status = 'activated', activated_at = datetime('now'), codex_reply = ?, activation_error = '', updated_at = datetime('now')
            WHERE id = ?
            """,
            (reply, inventory_id),
        )
        conn.execute(
            """
            UPDATE fulfillment_items
            SET status = 'activated', activation_reply = ?, activation_error = '', updated_at = datetime('now')
            WHERE order_id = ? AND inventory_id = ?
            """,
            (reply, order_id, inventory_id),
        )
    write_audit("inventory.activated", order_id=order_id, inventory_id=inventory_id, payload={"reply": reply[:500]})


def mark_activation_failed(inventory_id: int, order_id: str, error: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE inventory_items
            SET status = 'activation_failed', activation_error = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (error, inventory_id),
        )
        conn.execute(
            """
            UPDATE fulfillment_items
            SET status = 'activation_failed', activation_error = ?, updated_at = datetime('now')
            WHERE order_id = ? AND inventory_id = ?
            """,
            (error, order_id, inventory_id),
        )
    write_audit("inventory.activation_failed", order_id=order_id, inventory_id=inventory_id, payload={"error": error})


def account_block(item: dict[str, Any], index: int | None = None) -> str:
    title = f"账号{index}:" if index else "账号:"
    parts = [title]
    if item.get("email"):
        parts.append(f"邮箱：{item['email']}")
    return "\n".join(parts)


def render_delivery_text(items: list[dict[str, Any]]) -> str:
    template = get_setting("delivery_template")
    accounts = "\n\n".join(
        account_block(item, i + 1 if len(items) > 1 else None)
        for i, item in enumerate(items)
    )
    return template.replace("{accounts}", accounts).replace("{count}", str(len(items)))


def list_inventory(status: str = "", q: str = "", limit: int = 200) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if q:
        clauses.append("(email LIKE ? OR reserved_order_id LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM inventory_items{where} ORDER BY id DESC LIMIT ?",
            (*params, max(1, min(limit, 1000))),
        ).fetchall()
    result = []
    for row in rows:
        item = _hydrate_inventory_item(dict(row))
        ok, reason = is_eligible(item)
        activation_ok, activation_reason = activation_eligibility(item)
        item["eligible"] = ok
        item["eligible_reason"] = reason
        item["activation_eligible"] = activation_ok
        item["activation_eligible_reason"] = activation_reason
        oauth = desktop_oauth_status(item)
        item["desktop_oauth_ready"] = oauth["ready"]
        item["desktop_oauth_missing"] = oauth["missing"]
        item["credential_fields_present"] = {
            "access_token": bool(item.get("primary_token")),
            "refresh_token": bool(item.get("refresh_token")),
            "id_token": "id_token" not in oauth["missing"],
        }
        for secret_field in (
            "password", "primary_token", "id_token", "session_token", "refresh_token",
            "cookies", "source_payload",
        ):
            item.pop(secret_field, None)
        result.append(item)
    return result


def get_inventory_item(inventory_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (inventory_id,)).fetchone()
    return _hydrate_inventory_item(dict(row)) if row else None


def export_inventory_items(inventory_ids: list[int], format_name: str) -> Any:
    """Build credentials only for an explicit selected-inventory download."""
    if len(inventory_ids) > 1000:
        raise InventoryExportError("一次最多导出 1000 个库存账号")
    requested_ids = [int(value) for value in inventory_ids]
    if not requested_ids:
        raise InventoryExportError("请至少选择一个库存账号")
    unique_ids = list(dict.fromkeys(requested_ids))
    with connect() as conn:
        rows_by_id = {
            int(row["id"]): _hydrate_inventory_item(dict(row))
            for row in conn.execute(
                f"SELECT * FROM inventory_items WHERE id IN ({','.join('?' for _ in unique_ids)})",
                tuple(unique_ids),
            ).fetchall()
        }
    missing = next((inventory_id for inventory_id in unique_ids if inventory_id not in rows_by_id), None)
    if missing is not None:
        raise KeyError(f"库存不存在: {missing}")
    return build_inventory_export([rows_by_id[inventory_id] for inventory_id in unique_ids], format_name)


def export_inventory(inventory_ids: list[int], format_name: str) -> Any:
    """Short alias used by API integrations."""
    return export_inventory_items(inventory_ids, format_name)


def delete_inventory_item(inventory_id: int) -> dict[str, Any]:
    inventory_id = int(inventory_id)
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (inventory_id,)).fetchone()
        if not row:
            raise KeyError(f"库存不存在: {inventory_id}")
        item = dict(row)
        active_jobs = conn.execute(
            """
            SELECT id, status, stage FROM activation_jobs
            WHERE inventory_id = ? AND status NOT IN ('activated', 'failed', 'cancelled')
            ORDER BY id ASC
            """,
            (inventory_id,),
        ).fetchall()
        if active_jobs or str(item.get("status")) == "activating":
            stages = ", ".join(str(job["stage"] or job["status"]) for job in active_jobs) or "activating"
            raise InventoryDeleteBlocked(f"库存正在激活流程中，不能删除（{stages}）")

        batch_rows = conn.execute(
            "SELECT DISTINCT batch_id FROM activation_jobs WHERE inventory_id = ?",
            (inventory_id,),
        ).fetchall()
        batch_ids = [int(value["batch_id"]) for value in batch_rows]
        fulfillment_items = int(conn.execute(
            "SELECT COUNT(*) AS count FROM fulfillment_items WHERE inventory_id = ?",
            (inventory_id,),
        ).fetchone()["count"])
        activation_jobs = int(conn.execute(
            "SELECT COUNT(*) AS count FROM activation_jobs WHERE inventory_id = ?",
            (inventory_id,),
        ).fetchone()["count"])
        conn.execute("UPDATE fulfillments SET inventory_id = NULL, updated_at = datetime('now') WHERE inventory_id = ?", (inventory_id,))
        conn.execute("DELETE FROM fulfillment_items WHERE inventory_id = ?", (inventory_id,))
        conn.execute("DELETE FROM activation_jobs WHERE inventory_id = ?", (inventory_id,))
        deleted_batches = 0
        for batch_id in batch_ids:
            remaining = conn.execute("SELECT 1 FROM activation_jobs WHERE batch_id = ? LIMIT 1", (batch_id,)).fetchone()
            if remaining is None:
                deleted_batches += conn.execute("DELETE FROM activation_batches WHERE id = ?", (batch_id,)).rowcount
        conn.execute("DELETE FROM inventory_items WHERE id = ?", (inventory_id,))

    result = {
        "deleted": True,
        "inventory_id": inventory_id,
        "email": str(item.get("email") or ""),
        "previous_status": str(item.get("status") or ""),
        "removed_fulfillment_items": fulfillment_items,
        "removed_activation_jobs": activation_jobs,
        "removed_activation_batches": deleted_batches,
    }
    write_audit("inventory.deleted", order_id=str(item.get("reserved_order_id") or ""), inventory_id=inventory_id, payload=result)
    check_low_stock()
    return result


def bulk_delete_inventory_items(inventory_ids: list[int]) -> dict[str, Any]:
    """Delete each requested ID independently and keep blocked IDs isolated."""
    if len(inventory_ids) > 1000:
        raise ValueError("一次最多删除 1000 个库存账号")
    requested_ids = list(dict.fromkeys(int(value) for value in inventory_ids))
    details: list[dict[str, Any]] = []
    deleted = 0
    blocked = 0
    not_found = 0
    failed = 0
    for inventory_id in requested_ids:
        try:
            delete_inventory_item(inventory_id)
        except InventoryDeleteBlocked:
            blocked += 1
            details.append({"inventory_id": inventory_id, "status": "blocked", "reason": "delete_blocked"})
        except KeyError:
            not_found += 1
            details.append({"inventory_id": inventory_id, "status": "not_found", "reason": "inventory_not_found"})
        except Exception:
            failed += 1
            details.append({"inventory_id": inventory_id, "status": "failed", "reason": "delete_failed"})
        else:
            deleted += 1
            details.append({"inventory_id": inventory_id, "status": "deleted"})
    return {
        "requested": len(requested_ids),
        "deleted": deleted,
        "blocked": blocked,
        "not_found": not_found,
        "failed": failed,
        "details": details,
    }


def manual_update_status(inventory_id: int, status: str, order_id: str = "") -> dict[str, Any]:
    allowed = {"available", "shipped", "activating", "activated", "activation_failed", "reserved", "consumed"}
    if status not in allowed:
        raise RuntimeError(f"unsupported inventory status: {status}")
    order_id = (order_id or "").strip()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (inventory_id,)).fetchone()
        if not row:
            raise RuntimeError(f"inventory not found: {inventory_id}")
        current = dict(row)
        if status == "available":
            conn.execute(
                """
                UPDATE inventory_items
                SET status = 'available', reserved_order_id = '', shipped_at = NULL,
                    activation_error = '', updated_at = datetime('now')
                WHERE id = ?
                """,
                (inventory_id,),
            )
        else:
            if status in {"shipped", "activated", "activation_failed"} and not order_id:
                order_id = current.get("reserved_order_id") or f"manual-{status}-{inventory_id}"
            conn.execute(
                """
                UPDATE inventory_items
                SET status = ?, reserved_order_id = CASE WHEN ? = '' THEN reserved_order_id ELSE ? END,
                    shipped_at = CASE WHEN ? IN ('shipped', 'activated', 'activation_failed') THEN COALESCE(shipped_at, datetime('now')) ELSE shipped_at END,
                    activated_at = CASE WHEN ? = 'activated' THEN COALESCE(activated_at, datetime('now')) ELSE activated_at END,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (status, order_id, order_id, status, status, inventory_id),
            )
            if order_id and status in {"shipped", "activated", "activation_failed"}:
                conn.execute(
                    """
                    INSERT INTO fulfillments(order_id, buyer_id, item_id, quantity, status, delivery_text, updated_at)
                    VALUES (?, 'manual', 'manual', 1, ?, '', datetime('now'))
                    ON CONFLICT(order_id) DO UPDATE SET status = excluded.status, updated_at = datetime('now')
                    """,
                    (order_id, "activated" if status == "activated" else "account_sent"),
                )
                conn.execute(
                    """
                    INSERT INTO fulfillment_items(order_id, inventory_id, status)
                    VALUES (?, ?, ?)
                    ON CONFLICT(order_id, inventory_id) DO UPDATE SET status = excluded.status, updated_at = datetime('now')
                    """,
                    (order_id, inventory_id, "activated" if status == "activated" else "shipped"),
                )
    write_audit("inventory.manual_status", order_id=order_id, inventory_id=inventory_id, payload={"status": status})
    item = get_inventory_item(inventory_id)
    check_low_stock()
    return item or {}


def summary() -> dict[str, Any]:
    with connect() as conn:
        counts = conn.execute("SELECT status, COUNT(*) AS n FROM inventory_items GROUP BY status ORDER BY status").fetchall()
        rows = conn.execute("SELECT * FROM inventory_items WHERE status = 'available'").fetchall()
        alerts = conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 20").fetchall()
    eligible = sum(1 for row in rows if is_eligible(dict(row))[0])
    return {
        "by_status": {row["status"]: row["n"] for row in counts},
        "eligible": eligible,
        "alerts": [dict(row) for row in alerts],
    }


def check_low_stock() -> None:
    settings = get_settings()
    current = summary().get("eligible", 0)
    if current >= settings.low_stock_threshold:
        return
    with connect() as conn:
        conn.execute(
            "INSERT INTO alerts(kind, message, payload) VALUES ('low_stock', ?, ?)",
            (
                f"合格库存不足 {settings.low_stock_threshold} 个，当前 {current} 个",
                json.dumps({"eligible": current, "threshold": settings.low_stock_threshold}, ensure_ascii=False),
            ),
        )
