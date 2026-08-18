from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


WRAPPER_KEYS = ("accounts", "items", "data", "rows")
SUB2API_OPENAI_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"


class AccountFormatError(ValueError):
    """Raised when a JSON value does not contain an account record."""


class InventoryExportError(ValueError):
    """Raised for a safe, user-facing export validation failure."""


@dataclass(frozen=True)
class ParsedAccountPayload:
    accounts: list[dict[str, Any]]
    detected_formats: tuple[str, ...]
    skipped: int = 0


_CAMEL_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")
_SPACE_OR_DASH = re.compile(r"[\s-]+")
_JWT_B64 = re.compile(r"^[A-Za-z0-9_-]+$")


def _canonical_key(key: Any) -> str:
    value = str(key).strip()
    value = _SPACE_OR_DASH.sub("_", value)
    value = _CAMEL_BOUNDARY.sub(r"\1_\2", value)
    return value.lower()


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            normalized_key = _canonical_key(key)
            normalized_child = _canonicalize(child)
            if normalized_key not in result or result[normalized_key] in (None, "", [], {}):
                result[normalized_key] = normalized_child
        return result
    if isinstance(value, list):
        return [_canonicalize(child) for child in value]
    if isinstance(value, tuple):
        return [_canonicalize(child) for child in value]
    return value


def _text(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()


def _json_values_from_text(text: str) -> list[Any]:
    value = str(text or "").strip()
    if not value:
        return []
    value = re.sub(r"```(?:json|JSON)?", "", value).strip()
    try:
        return [json.loads(value)]
    except json.JSONDecodeError:
        pass

    token_values: list[Any] = []
    token_lines = [line.strip() for line in value.splitlines() if line.strip()]
    if token_lines and all(not line.startswith(("{", "[")) for line in token_lines):
        for line in token_lines:
            try:
                token_values.append(json.loads(line))
            except json.JSONDecodeError:
                if line.startswith("rt."):
                    token_values.append({"refresh_token": line})
                elif line.startswith("at-") or len(line.split(".")) >= 2:
                    token_values.append({"access_token": line})
                else:
                    token_values = []
                    break
        if token_values:
            return token_values

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


def _looks_like_record(value: Mapping[str, Any]) -> bool:
    record_keys = {
        "id",
        "email",
        "name",
        "account_name",
        "account_id",
        "user_id",
        "platform",
        "type",
        "auth_mode",
        "openai_api_key",
        "access_token",
        "primary_token",
        "refresh_token",
        "id_token",
        "tokens",
        "credentials",
        "oauth",
        "auth",
        "agent_identity",
    }
    return any(key in value for key in record_keys)


def _is_sub2api_document(value: Mapping[str, Any]) -> bool:
    if _text(value.get("type")).lower() == "sub2api-data":
        return True
    accounts = value.get("accounts")
    if isinstance(accounts, list):
        return any(
            isinstance(item, dict)
            and _text(_canonicalize(item).get("platform")).lower() == "openai"
            and _text(_canonicalize(item).get("type")).lower() in {"oauth", "apikey", "api_key", "api-key"}
            for item in accounts
        )
    return False


def _iter_wrapper_values(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        canonical = _canonicalize(value)
        if _looks_like_record(canonical):
            return [value]
        return list(value.values())
    if isinstance(value, str):
        return [value]
    return []


def _collect_records(value: Any, *, sub2api: bool = False) -> list[tuple[dict[str, Any], bool]]:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise AccountFormatError("账号 JSON 必须使用 UTF-8 编码") from exc

    if isinstance(value, str):
        parsed_values = _json_values_from_text(value)
        if not parsed_values:
            raise AccountFormatError("账号 JSON 解析失败")
        records: list[tuple[dict[str, Any], bool]] = []
        for parsed in parsed_values:
            records.extend(_collect_records(parsed, sub2api=sub2api))
        return records

    if isinstance(value, list):
        records = []
        for item in value:
            records.extend(_collect_records(item, sub2api=sub2api))
        return records

    if not isinstance(value, dict):
        raise AccountFormatError("账号 JSON 必须是对象、数组或 JSON 文本")

    canonical = _canonicalize(value)
    current_sub2api = sub2api or _is_sub2api_document(canonical)
    wrapped: list[tuple[dict[str, Any], bool]] = []
    found_wrapper = False
    for key in WRAPPER_KEYS:
        if key not in canonical:
            continue
        found_wrapper = True
        for child in _iter_wrapper_values(canonical[key]):
            wrapped.extend(_collect_records(child, sub2api=current_sub2api))
    if found_wrapper:
        return wrapped

    if not _looks_like_record(canonical):
        nested: list[tuple[dict[str, Any], bool]] = []
        for child in canonical.values():
            try:
                nested.extend(_collect_records(child, sub2api=current_sub2api))
            except AccountFormatError:
                continue
        if nested:
            return nested
        raise AccountFormatError("没有识别到有效账号 JSON")

    return [(canonical, current_sub2api)]


def _is_api_key_record(record: Mapping[str, Any]) -> bool:
    auth_mode = _text(record.get("auth_mode")).lower().replace("-", "_")
    record_type = _text(record.get("type")).lower().replace("-", "_")
    if auth_mode in {"apikey", "api_key", "api_key_auth"}:
        return True
    if record_type in {"apikey", "api_key"}:
        return True
    has_access = any(
        _text(record.get(key))
        for key in ("access_token", "primary_token", "refresh_token", "id_token")
    )
    return bool(_text(record.get("openai_api_key")) and not has_access and not record.get("agent_identity"))


def _is_sub2api_oauth(record: Mapping[str, Any]) -> bool:
    return (
        _text(record.get("platform")).lower() == "openai"
        and _text(record.get("type")).lower() == "oauth"
    )


def detect_account_format(payload: Any) -> str:
    """Return the first recognized source format without exposing payload data."""
    records = _collect_records(payload)
    if not records:
        return "unknown"
    record, is_sub2api = records[0]
    if is_sub2api:
        return "sub2api"
    if record.get("auth_mode") is not None or record.get("agent_identity") is not None:
        return "auth_json"
    if record.get("type") == "codex" or record.get("last_refresh") is not None:
        return "cockpit_tools"
    if any(key in record for key in ("tokens", "credentials", "oauth", "auth")):
        return "account_json"
    return "cpa"


def parse_account_payload(payload: Any) -> ParsedAccountPayload:
    """Parse CPA, Sub2API, Cockpit Tools, auth.json, and generic account JSON."""
    collected = _collect_records(payload)
    accounts: list[dict[str, Any]] = []
    formats: list[str] = []
    skipped = 0
    for record, is_sub2api in collected:
        source_format = "sub2api" if is_sub2api else detect_account_format(record)
        if is_sub2api:
            if not _is_sub2api_oauth(record):
                skipped += 1
                continue
        elif _is_api_key_record(record):
            skipped += 1
            continue
        accounts.append(record)
        if source_format not in formats:
            formats.append(source_format)
    if collected and not accounts and skipped:
        return ParsedAccountPayload([], tuple(formats), skipped)
    if not collected and payload not in ([], "", None):
        raise AccountFormatError("没有识别到有效账号 JSON")
    return ParsedAccountPayload(accounts, tuple(formats), skipped)


def parse_account_json(payload: Any) -> list[dict[str, Any]]:
    """Compatibility-friendly list-returning parser for callers that need records."""
    return parse_account_payload(payload).accounts


def parse_inventory_payload(payload: Any) -> ParsedAccountPayload:
    return parse_account_payload(payload)


def parse_inventory_accounts(payload: Any) -> list[dict[str, Any]]:
    return parse_account_json(payload)


def _as_sources(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    row_map = _canonicalize(dict(row))
    if isinstance(row_map, dict):
        sources.append(row_map)
        source_payload = row_map.get("source_payload")
        if isinstance(source_payload, str):
            try:
                decoded = json.loads(source_payload)
            except (TypeError, ValueError, json.JSONDecodeError):
                decoded = None
            if isinstance(decoded, dict):
                sources.append(_canonicalize(decoded))
    index = 0
    while index < len(sources):
        source = sources[index]
        for key in ("credentials", "tokens", "oauth", "auth", "agent_identity"):
            value = source.get(key)
            if isinstance(value, dict):
                child = _canonicalize(value)
                if child not in sources:
                    sources.append(child)
        index += 1
    return sources


def _pick_sources(sources: Sequence[Mapping[str, Any]], *keys: str) -> Any:
    canonical_keys = tuple(_canonical_key(key) for key in keys)
    for source in sources:
        for key in canonical_keys:
            value = source.get(key)
            if value not in (None, "", [], {}):
                return value
    return ""


def _parse_expiry(value: Any) -> datetime | None:
    if value in (None, "") or isinstance(value, bool):
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


def _timestamp_iso(value: Any, *, fallback_now: bool = False) -> str:
    parsed = _parse_expiry(value)
    if parsed is not None:
        return parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    text = _text(value)
    if text:
        return text
    if fallback_now:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return ""


def _decode_jwt_payload(token: Any) -> dict[str, Any]:
    candidate = _text(token)
    if candidate.lower().startswith("bearer "):
        candidate = candidate[7:].strip()
    parts = candidate.split(".")
    if len(parts) < 2 or not _JWT_B64.fullmatch(parts[1]):
        return {}
    try:
        encoded = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(encoded.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, base64.binascii.Error):
        return {}
    return payload if isinstance(payload, dict) else {}


def _claim_value(claims: Mapping[str, Any], *keys: str) -> Any:
    maps: list[Mapping[str, Any]] = [claims]
    for key in ("https://api.openai.com/auth", "https://api.openai.com/profile", "auth", "profile", "user"):
        value = claims.get(key)
        if isinstance(value, dict):
            maps.append(value)
    return _pick_sources(maps, *keys)


def _export_view(row: Mapping[str, Any]) -> dict[str, Any]:
    sources = _as_sources(row)
    access_token = _text(_pick_sources(sources, "primary_token", "access_token", "token"))
    refresh_token = _text(_pick_sources(sources, "refresh_token"))
    id_token = _text(_pick_sources(sources, "id_token"))
    claims = _decode_jwt_payload(access_token)
    id_claims = _decode_jwt_payload(id_token)
    email = _text(_pick_sources(sources, "email", "account", "username", "name"))
    account_id = _text(_pick_sources(sources, "account_id", "chatgpt_account_id"))
    account_id = account_id or _text(_claim_value(id_claims, "chatgpt_account_id", "account_id"))
    account_id = account_id or _text(_claim_value(claims, "chatgpt_account_id", "account_id"))
    user_id = _text(_pick_sources(sources, "user_id", "chatgpt_user_id"))
    user_id = user_id or _text(_claim_value(id_claims, "chatgpt_user_id", "user_id", "sub"))
    user_id = user_id or _text(_claim_value(claims, "chatgpt_user_id", "user_id", "sub"))
    organization_id = _text(_pick_sources(sources, "organization_id", "org_id"))
    organization_id = organization_id or _text(_claim_value(id_claims, "organization_id", "poid"))
    organization_id = organization_id or _text(_claim_value(claims, "organization_id", "poid"))
    plan_type = _text(_pick_sources(sources, "plan_type", "chatgpt_plan_type"))
    plan_type = plan_type or _text(_claim_value(id_claims, "chatgpt_plan_type", "plan_type"))
    plan_type = plan_type or _text(_claim_value(claims, "chatgpt_plan_type", "plan_type"))
    expiry = _pick_sources(sources, "expires_at", "expired")
    expiry_iso = _timestamp_iso(expiry)
    if not expiry_iso:
        expiry_iso = _timestamp_iso(_claim_value(claims, "exp"))
    subscription_expires_at = _timestamp_iso(
        _pick_sources(sources, "subscription_expires_at", "subscription_active_until")
    )
    source = sources[1] if len(sources) > 1 else sources[0]
    identity = source.get("agent_identity") if isinstance(source, dict) else None
    if not isinstance(identity, dict):
        identity = None
    openai_api_key = _text(_pick_sources(sources, "openai_api_key"))
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "id_token": id_token,
        "email": email.lower() if "@" in email else email,
        "account_id": account_id,
        "user_id": user_id,
        "organization_id": organization_id,
        "plan_type": plan_type,
        "expires_at": expiry_iso,
        "subscription_expires_at": subscription_expires_at,
        "last_refresh": _timestamp_iso(_pick_sources(sources, "last_refresh", "token_updated_at", "updated_at"), fallback_now=True),
        "account_name": _text(_pick_sources(sources, "account_name")),
        "account_structure": _text(_pick_sources(sources, "account_structure")),
        "auth_mode": _text(_pick_sources(sources, "auth_mode")),
        "openai_api_key": openai_api_key,
        "codex_fingerprint_mode": _text(_pick_sources(sources, "codex_fingerprint_mode")),
        "identity": identity,
        "identity_source": source,
        "row_id": _text(row.get("id")),
    }


def _agent_identity_credentials(view: Mapping[str, Any]) -> dict[str, Any]:
    identity = view.get("identity")
    if not isinstance(identity, dict):
        raise InventoryExportError("Agent Identity 凭证不完整")
    runtime_id = _text(identity.get("agent_runtime_id"))
    private_key = _text(identity.get("agent_private_key"))
    account_id = _text(identity.get("account_id")) or _text(view.get("account_id"))
    user_id = _text(identity.get("chatgpt_user_id")) or _text(view.get("user_id"))
    if not runtime_id or not private_key or not account_id or not user_id:
        raise InventoryExportError("Agent Identity 凭证不完整")
    credentials: dict[str, Any] = {
        "auth_mode": "agentIdentity",
        "agent_runtime_id": runtime_id,
        "agent_private_key": private_key,
        "account_id": account_id,
        "chatgpt_account_id": account_id,
        "chatgpt_user_id": user_id,
        "chatgpt_account_is_fedramp": bool(identity.get("chatgpt_account_is_fedramp", False)),
    }
    for key in ("task_id", "email", "plan_type"):
        value = _text(identity.get(key)) or (_text(view.get(key)) if key != "task_id" else "")
        if value:
            credentials[key] = value
    return credentials


def _to_cockpit_tools_account(row: Mapping[str, Any]) -> dict[str, Any]:
    view = _export_view(row)
    if view["identity"] is not None:
        credentials = _agent_identity_credentials(view)
        payload: dict[str, Any] = {
            "auth_mode": "agentIdentity",
            "agent_identity": credentials,
            "account_id": str(credentials["account_id"]),
            "user_id": str(credentials["chatgpt_user_id"]),
            "email": str(credentials.get("email") or view["email"]),
            "type": "codex",
        }
        for key in ("plan_type", "account_name", "account_structure"):
            if view[key]:
                payload[key] = view[key]
        return payload
    if view["auth_mode"].lower().replace("-", "_") in {"apikey", "api_key"} and view["openai_api_key"]:
        payload = {
            "auth_mode": "apikey",
            "OPENAI_API_KEY": view["openai_api_key"],
            "email": view["email"],
        }
        return payload
    return {
        "id_token": view["id_token"],
        "access_token": view["access_token"],
        "refresh_token": view["refresh_token"],
        "account_id": view["account_id"],
        "last_refresh": view["last_refresh"],
        "email": view["email"],
        "type": "codex",
        "expired": view["expires_at"],
    }


def _to_sub2api_account(row: Mapping[str, Any]) -> dict[str, Any]:
    view = _export_view(row)
    if view["identity"] is not None:
        credentials = _agent_identity_credentials(view)
    else:
        if not view["access_token"]:
            raise InventoryExportError("OAuth 账号缺少 access_token")
        credentials = {"access_token": view["access_token"]}
        if view["expires_at"]:
            credentials["expires_at"] = view["expires_at"]
        if view["refresh_token"]:
            credentials["refresh_token"] = view["refresh_token"]
            credentials["client_id"] = SUB2API_OPENAI_CLIENT_ID
        if view["id_token"]:
            credentials["id_token"] = view["id_token"]
        for key in (
            "email",
            "account_id",
            "user_id",
            "organization_id",
            "plan_type",
            "subscription_expires_at",
        ):
            value = view[key]
            if value:
                output_key = "chatgpt_account_id" if key == "account_id" else "chatgpt_user_id" if key == "user_id" else key
                credentials[output_key] = value
    name = view["account_name"] or view["email"] or view["account_id"] or view["row_id"] or "account"
    account = {
        "name": name,
        "platform": "openai",
        "type": "oauth",
        "credentials": credentials,
        "concurrency": 3,
        "priority": 50,
    }
    if view["identity"] is None and not view["refresh_token"] and view["expires_at"]:
        expires_at = _parse_expiry(view["expires_at"])
        if expires_at is not None:
            account["expires_at"] = int(expires_at.timestamp())
            account["auto_pause_on_expired"] = True
    return account


def _to_cpa_account(row: Mapping[str, Any]) -> dict[str, Any]:
    view = _export_view(row)
    if view["identity"] is not None:
        raise InventoryExportError("CPA 格式不支持 Agent Identity 账号")
    return {
        "id_token": view["id_token"],
        "access_token": view["access_token"],
        "refresh_token": view["refresh_token"],
        "account_id": view["account_id"],
        "last_refresh": view["last_refresh"],
        "email": view["email"],
        "type": "codex",
        "expired": view["expires_at"],
    }


def build_inventory_export(rows: Sequence[Mapping[str, Any]], format_name: str) -> Any:
    """Build an explicit-download payload; callers must not log the return value."""
    normalized_format = _text(format_name).lower().replace("-", "_")
    if normalized_format not in {"cockpit_tools", "sub2api", "cpa"}:
        raise InventoryExportError("不支持的导出格式")
    if normalized_format == "cockpit_tools":
        return [_to_cockpit_tools_account(row) for row in rows]
    if normalized_format == "sub2api":
        return {
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "proxies": [],
            "accounts": [_to_sub2api_account(row) for row in rows],
            "type": "sub2api-data",
            "version": 1,
        }
    accounts = [_to_cpa_account(row) for row in rows]
    return accounts[0] if len(accounts) == 1 else accounts


def serialize_inventory_export(rows: Sequence[Mapping[str, Any]], format_name: str) -> str:
    payload = build_inventory_export(rows, format_name)
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
