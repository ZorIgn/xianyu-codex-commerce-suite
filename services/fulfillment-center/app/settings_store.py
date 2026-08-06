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
    "activation_provider": "ACTIVATION_PROVIDER",
    "reauth_before_activation": "REAUTH_BEFORE_ACTIVATION",
    "desktop_instance_id": "DESKTOP_INSTANCE_ID",
    "desktop_instance_name": "DESKTOP_INSTANCE_NAME",
    "desktop_profile_dir": "DESKTOP_PROFILE_DIR",
    "desktop_app_user_data_dir": "DESKTOP_APP_USER_DATA_DIR",
    "desktop_launch_command": "DESKTOP_LAUNCH_COMMAND",
    "desktop_instance_pool": "DESKTOP_INSTANCE_POOL",
    "activation_worker_count": "ACTIVATION_WORKER_COUNT",
    "desktop_background_mode": "DESKTOP_BACKGROUND_MODE",
    "desktop_allow_foreground_fallback": "DESKTOP_ALLOW_FOREGROUND_FALLBACK",
    "delivery_worker_count": "DELIVERY_WORKER_COUNT",
    "delivery_retry_limit": "DELIVERY_RETRY_LIMIT",
    "delivery_retry_base_seconds": "DELIVERY_RETRY_BASE_SECONDS",
    "delivery_poll_seconds": "DELIVERY_POLL_SECONDS",
    "oauth_reauth_retry_limit": "OAUTH_REAUTH_RETRY_LIMIT",
    "oauth_reauth_retry_delays": "OAUTH_REAUTH_RETRY_DELAYS",
    "oauth_reauth_retry_delay_seconds": "OAUTH_REAUTH_RETRY_DELAY_SECONDS",
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
    value = getattr(settings, key, default)
    return str(value if value is not None else default)


def get_all_settings() -> dict[str, str]:
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings ORDER BY key").fetchall()
    data = {row["key"]: row["value"] for row in rows}
    settings = get_settings()
    for key in ENV_FALLBACKS:
        if not data.get(key):
            data[key] = get_setting(key, "false" if key == "reauth_before_activation" else "")
    data.setdefault("activation_provider", settings.activation_provider)
    data.setdefault("reauth_before_activation", get_setting("reauth_before_activation", "false"))
    data.setdefault("desktop_instance_name", settings.desktop_instance_name)
    data.setdefault("desktop_instance_id", settings.desktop_instance_id)
    data.setdefault("desktop_profile_dir", str(settings.desktop_profile_dir or ""))
    data.setdefault("desktop_app_user_data_dir", str(settings.desktop_app_user_data_dir or ""))
    data.setdefault("desktop_launch_command", settings.desktop_launch_command)
    data.setdefault("desktop_instance_pool", get_setting("desktop_instance_pool", settings.desktop_instance_pool))
    data.setdefault("activation_worker_count", str(settings.activation_worker_count))
    data.setdefault("desktop_background_mode", "true" if settings.desktop_background_mode else "false")
    data.setdefault("oauth_reauth_retry_limit", str(settings.oauth_reauth_retry_limit))
    data.setdefault("oauth_reauth_retry_delay_seconds", str(settings.oauth_reauth_retry_delay_seconds))
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
        "activation_provider",
        "reauth_before_activation",
        "desktop_instance_id",
        "desktop_instance_name",
        "desktop_profile_dir",
        "desktop_app_user_data_dir",
        "desktop_launch_command",
        "desktop_instance_pool",
        "activation_worker_count",
        "desktop_background_mode",
        "desktop_allow_foreground_fallback",
        "delivery_worker_count",
        "delivery_retry_limit",
        "delivery_retry_base_seconds",
        "delivery_poll_seconds",
        "oauth_reauth_retry_limit",
        "oauth_reauth_retry_delays",
        "oauth_reauth_retry_delay_seconds",
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
