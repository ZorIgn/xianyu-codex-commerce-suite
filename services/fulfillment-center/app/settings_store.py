from __future__ import annotations

import os
from typing import Any

from .config import get_settings
from .db import connect


ENV_FALLBACKS = {
    "xianyu_base_url": "XIANYU_BASE_URL",
    "xianyu_api_token": "XIANYU_API_TOKEN",
    "cockpit_base_url": "COCKPIT_BASE_URL",
    "cockpit_api_token": "COCKPIT_API_TOKEN",
    "codex_command": "CODEX_COMMAND",
}


def get_setting(key: str, default: str = "") -> str:
    with connect() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    if row and row["value"] != "":
        return str(row["value"])
    env_name = ENV_FALLBACKS.get(key)
    if env_name:
        return os.getenv(env_name, default)
    settings = get_settings()
    return str(getattr(settings, key, default) or default)


def get_all_settings() -> dict[str, str]:
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings ORDER BY key").fetchall()
    data = {row["key"]: row["value"] for row in rows}
    for key in ENV_FALLBACKS:
        data.setdefault(key, get_setting(key, ""))
    return data


def update_settings(values: dict[str, Any]) -> dict[str, str]:
    allowed = {
        "delivery_template",
        "xianyu_send_endpoint",
        "xianyu_account_id",
        "xianyu_base_url",
        "xianyu_api_token",
        "cockpit_base_url",
        "cockpit_api_token",
        "codex_command",
        "codex_prompt",
    }
    with connect() as conn:
        for key, value in values.items():
            if key not in allowed:
                continue
            conn.execute(
                """
                INSERT INTO app_settings(key, value, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
                """,
                (key, str(value or "")),
            )
    return get_all_settings()
