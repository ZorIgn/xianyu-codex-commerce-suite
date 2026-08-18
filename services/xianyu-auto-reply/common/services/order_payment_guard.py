"""Pure helpers for the payment/amount gate used by automatic delivery.

The order metadata JSON stores the state produced by these helpers.  Keeping
the decision and backoff calculation free of database/network dependencies
makes the race behavior easy to test without real orders or credentials.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any


PAYMENT_GUARD_METADATA_KEY = "auto_delivery_payment_guard"
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BASE_DELAY_SECONDS = 1.0
DEFAULT_MAX_DELAY_SECONDS = 8.0
# Keep operator-provided values bounded even when the environment file is
# malformed or contains an accidentally huge number.
MAX_ALLOWED_ATTEMPTS = 16
MAX_ALLOWED_DELAY_SECONDS = 60.0


@dataclass(frozen=True)
class PaymentGuardDecision:
    """Decision returned before any stock allocation or buyer message."""

    action: str
    reason: dict[str, Any]


def parse_amount(value: Any) -> Decimal | None:
    """Return a normalized amount, or ``None`` when the value is unknown."""

    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not amount.is_finite():
        return None
    return amount


def _status_text(*values: Any) -> str:
    return " ".join(str(value or "") for value in values).lower()


def classify_terminal_reason(
    *,
    status_reason: str | None = None,
    platform_status: str | None = None,
    local_status: str | None = None,
) -> dict[str, str] | None:
    """Map a known platform/local terminal state to a stable reason code."""

    text = _status_text(status_reason, platform_status, local_status)
    status_values = {
        str(value or "").strip().lower()
        for value in (platform_status, local_status)
        if value is not None
    }
    status_reason_text = str(status_reason or "").lower()

    standard_terminal_values = {
        "shipped": ("already_shipped", "订单已发货，跳过重复发货"),
        "refunded": ("order_refunded", "订单已退款或正在退款，停止自动发货"),
        "refunding": ("order_refunded", "订单已退款或正在退款，停止自动发货"),
        "refund": ("order_refunded", "订单已退款或正在退款，停止自动发货"),
        "order_refunded": ("order_refunded", "订单已退款或正在退款，停止自动发货"),
        "closed": ("order_closed", "订单已关闭，停止自动发货"),
        "order_closed": ("order_closed", "订单已关闭，停止自动发货"),
        "trade_closed": ("order_closed", "订单已关闭，停止自动发货"),
        "cancelled": ("order_cancelled", "订单已取消，停止自动发货"),
        "canceled": ("order_cancelled", "订单已取消，停止自动发货"),
        "order_cancelled": ("order_cancelled", "订单已取消，停止自动发货"),
        "trade_cancelled": ("order_cancelled", "订单已取消，停止自动发货"),
        "completed": ("transaction_completed", "交易已完成，停止自动发货"),
        "transaction_completed": ("transaction_completed", "交易已完成，停止自动发货"),
        "trade_completed": ("transaction_completed", "交易已完成，停止自动发货"),
    }
    for status_value in status_values:
        terminal_value = standard_terminal_values.get(status_value)
        if terminal_value:
            return {"code": terminal_value[0], "message": terminal_value[1]}

    if any(
        phrase in text
        for phrase in (
            "订单已发货",
            "交易已发货",
            "订单发货成功",
            "order shipped",
            "transaction shipped",
        )
    ):
        return {"code": "already_shipped", "message": "订单已发货，跳过重复发货"}
    if any(
        keyword in text
        for keyword in ("订单退款", "订单已退款", "退款中", "退款成功", "order refunded", "refunding")
    ):
        return {"code": "order_refunded", "message": "订单已退款或正在退款，停止自动发货"}
    if any(
        keyword in text
        for keyword in ("交易关闭", "订单关闭", "订单已关闭", "order closed", "trade closed")
    ):
        return {"code": "order_closed", "message": "订单已关闭，停止自动发货"}
    if any(
        keyword in text
        for keyword in ("交易取消", "订单取消", "订单已取消", "order cancelled", "order canceled", "trade cancelled")
    ):
        return {"code": "order_cancelled", "message": "订单已取消，停止自动发货"}
    # Do not treat a generic API/network message such as "获取订单详情失败"
    # as a transaction terminal state.  Only explicit payment/trade failure
    # wording or a standard status value can stop the bounded refresh retry.
    explicit_failure_phrases = (
        "交易失败",
        "支付失败",
        "付款失败",
        "交易或支付已失败",
        "交易或支付失败",
        "transaction failed",
        "payment failed",
        "trade failed",
    )
    standard_failure_values = {
        "failed",
        "transaction_failed",
        "payment_failed",
        "trade_failed",
    }
    if any(keyword in status_reason_text for keyword in explicit_failure_phrases) or (
        status_values & standard_failure_values
    ):
        return {"code": "transaction_failed", "message": "交易或支付已失败，停止自动发货"}
    if any(
        keyword in text
        for keyword in ("交易成功", "交易完成", "订单已完成", "transaction completed", "order completed")
    ):
        return {"code": "transaction_completed", "message": "交易已完成，停止自动发货"}
    return None


def classify_payment_state(
    *,
    amount: Any,
    can_ship: bool | None,
    status_reason: str | None = None,
    platform_status: str | None = None,
    local_status: str | None = None,
    amount_authoritative: bool = False,
) -> PaymentGuardDecision:
    """Classify a refreshed order without allocating inventory.

    A local zero is intentionally not treated as a real zero here.  Until the
    platform detail/status refresh is authoritative, it is a retryable sync
    condition.  The bounded retry state turns an unchanged zero into an
    explicit ``zero_amount_confirmed`` terminal reason.
    """

    terminal_reason = classify_terminal_reason(
        status_reason=status_reason,
        platform_status=platform_status,
        local_status=local_status,
    )
    if terminal_reason:
        action = "already_shipped" if terminal_reason["code"] == "already_shipped" else "stop"
        return PaymentGuardDecision(action=action, reason=terminal_reason)

    normalized_amount = parse_amount(amount)
    if can_ship is True and normalized_amount is not None and normalized_amount > 0:
        return PaymentGuardDecision(
            action="proceed",
            reason={
                "code": "amount_synced",
                "message": "订单金额已同步且订单处于已付款待发货状态",
                "amount": str(normalized_amount),
            },
        )

    if normalized_amount is None or normalized_amount <= 0:
        return PaymentGuardDecision(
            action="retry",
            reason={
                "code": "amount_not_synced",
                "message": "订单金额尚未同步为可发货正金额",
                "amount": str(normalized_amount) if normalized_amount is not None else None,
                "amount_authoritative": bool(amount_authoritative),
            },
        )

    return PaymentGuardDecision(
        action="retry",
        reason={
            "code": "order_not_ready",
            "message": "订单尚未确认处于已付款待发货状态",
            "amount": str(normalized_amount),
        },
    )


def _now_utc(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None


def _safe_positive_float(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if math.isfinite(parsed) and parsed > 0 else fallback


def _safe_max_attempts(value: Any, fallback: int = DEFAULT_MAX_ATTEMPTS) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return min(MAX_ALLOWED_ATTEMPTS, max(1, parsed))


def normalize_retry_config(
    max_attempts: Any = DEFAULT_MAX_ATTEMPTS,
    base_delay_seconds: Any = DEFAULT_BASE_DELAY_SECONDS,
    max_delay_seconds: Any = DEFAULT_MAX_DELAY_SECONDS,
) -> tuple[int, float, float]:
    """Normalize retry settings to finite, positive operational limits."""

    attempts = _safe_max_attempts(max_attempts)
    base_delay = min(
        MAX_ALLOWED_DELAY_SECONDS,
        _safe_positive_float(base_delay_seconds, DEFAULT_BASE_DELAY_SECONDS),
    )
    max_delay = min(
        MAX_ALLOWED_DELAY_SECONDS,
        max(base_delay, _safe_positive_float(max_delay_seconds, DEFAULT_MAX_DELAY_SECONDS)),
    )
    return attempts, base_delay, max_delay


def _previous_attempt(previous: dict[str, Any] | None) -> int:
    try:
        return max(0, int((previous or {}).get("attempt", 0)))
    except (TypeError, ValueError):
        return 0


def build_retry_state(
    previous: dict[str, Any] | None,
    reason: dict[str, Any],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS,
    now: datetime | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Advance a finite exponential-backoff state and persistable audit data."""

    current_time = _now_utc(now)
    max_attempts, base_delay, max_delay = normalize_retry_config(
        max_attempts,
        base_delay_seconds,
        max_delay_seconds,
    )
    attempt = _previous_attempt(previous) + 1
    reason = dict(reason)
    reason.setdefault("code", "payment_sync_pending")

    state: dict[str, Any] = {
        "version": 1,
        "state": "retrying",
        "attempt": attempt,
        "max": max_attempts,
        "next_retry": None,
        "reason": reason,
        "updated_at": _iso(current_time),
    }
    if context:
        state["context"] = dict(context)

    if attempt >= max_attempts:
        last_code = reason.get("code")
        if last_code == "amount_not_synced":
            last_amount = parse_amount(reason.get("amount"))
            terminal_code = (
                "zero_amount_confirmed"
                if reason.get("amount_authoritative") is True
                and last_amount is not None
                and last_amount == 0
                else "amount_sync_retry_exhausted"
            )
            terminal_message = (
                "订单详情在有限重试后仍确认金额为0，停止自动发货"
                if terminal_code == "zero_amount_confirmed"
                else "订单金额在有限重试后仍未同步，停止自动发货"
            )
        else:
            terminal_code = "payment_sync_retry_exhausted"
            terminal_message = "订单付款/发货状态在有限重试后仍未确认，停止自动发货"
        state["state"] = "stopped"
        state["reason"] = {
            "code": terminal_code,
            "message": terminal_message,
            "last_code": last_code,
        }
        return state

    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
    state["next_retry"] = _iso(current_time + timedelta(seconds=delay))
    state["retry_after_seconds"] = delay
    return state


def build_terminal_state(
    previous: dict[str, Any] | None,
    reason: dict[str, Any],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    now: datetime | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a non-retryable terminal state."""

    state: dict[str, Any] = {
        "version": 1,
        "state": "stopped",
        "attempt": _previous_attempt(previous),
        "max": _safe_max_attempts(max_attempts),
        "next_retry": None,
        "reason": dict(reason),
        "updated_at": _iso(_now_utc(now)),
    }
    if context:
        state["context"] = dict(context)
    return state


def build_ready_state(
    previous: dict[str, Any] | None,
    *,
    amount: Any,
    platform_status: str | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    now: datetime | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record that the payment gate passed and no retry is due."""

    normalized_amount = parse_amount(amount)
    state: dict[str, Any] = {
        "version": 1,
        "state": "ready",
        "attempt": _previous_attempt(previous),
        "max": _safe_max_attempts(max_attempts),
        "next_retry": None,
        "reason": {
            "code": "amount_synced",
            "message": "订单金额已同步且订单处于已付款待发货状态",
            "amount": str(normalized_amount) if normalized_amount is not None else None,
            "platform_status": platform_status,
        },
        "updated_at": _iso(_now_utc(now)),
    }
    if context:
        state["context"] = dict(context)
    return state


def is_retry_due(state: dict[str, Any] | None, *, now: datetime | None = None) -> bool:
    """Return whether a persisted retry is due now."""

    if not state or state.get("state") != "retrying":
        return False
    next_retry = state.get("next_retry")
    if not next_retry:
        return True
    try:
        retry_time = datetime.fromisoformat(str(next_retry).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    return retry_time <= _now_utc(now)


def format_guard_reason(state: dict[str, Any]) -> str:
    """Return a short human-readable reason for the existing order column."""

    reason = state.get("reason") or {}
    message = reason.get("message") or reason.get("code") or "自动发货付款状态未确认"
    if state.get("state") == "retrying":
        return (
            f"{message}（第{state.get('attempt', 0)}/{state.get('max', 0)}次，"
            f"next_retry={state.get('next_retry')}）"
        )
    return str(message)
