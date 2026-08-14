from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ActivationResult:
    """三个激活提供方（CLI / 桌面端 / WebSocket）共用的结果语义。

    ``sent_unknown=True`` 表示“你好”可能已经送达，队列必须停止自动重试，
    转入人工复核，避免重复激活。
    """

    ok: bool
    reply: str = ""
    error: str = ""
    stage: str = ""
    sent_unknown: bool = False
    provider: str = ""
    thread_id: str = ""
    turn_id: str = ""
    model: str = ""
    attempts: int = 0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        return result


def result_dict(
    *,
    ok: bool,
    reply: str = "",
    error: str = "",
    stage: str = "",
    sent_unknown: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    """构建与历史 Provider 返回结构兼容的字典。

    ``extra`` 可用于附加传输信息（thread_id/turn_id/model/attempts 等），
    队列会忽略未知字段，仅用于审计与排查。
    """
    payload: dict[str, Any] = {
        "ok": ok,
        "reply": reply,
        "error": error,
        "stage": stage,
        "sent_unknown": sent_unknown,
    }
    payload.update({key: value for key, value in extra.items() if value not in (None, "")})
    return payload


def result_from_object(result: ActivationResult) -> dict[str, Any]:
    data = asdict(result)
    return {key: value for key, value in data.items() if value not in (None, "")}


__all__ = [
    "ActivationResult",
    "result_dict",
    "result_from_object",
]
