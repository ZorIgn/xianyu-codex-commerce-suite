from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_path: Path
    low_stock_threshold: int
    max_reset_count: int
    cpa_platform: str
    cockpit_base_url: str
    cockpit_api_token: str
    xianyu_base_url: str
    xianyu_api_token: str
    codex_command: str
    codex_timeout_seconds: int
    dry_run: bool
    activation_provider: str
    cockpit_state_dir: Path
    desktop_instance_id: str
    desktop_instance_name: str
    desktop_profile_dir: Path | None
    desktop_app_user_data_dir: Path | None
    desktop_launch_command: str
    activation_poll_seconds: float
    desktop_start_timeout_seconds: int
    desktop_response_timeout_seconds: int
    desktop_retry_limit: int
    desktop_idle_timeout_seconds: int
    desktop_autoclose: bool
    desktop_require_account_verification: bool
    desktop_instance_pool: str
    activation_worker_count: int
    desktop_background_mode: bool
    desktop_allow_foreground_fallback: bool
    ws_base_url: str
    ws_proxy_url: str
    ws_model: str
    ws_originator: str
    ws_client_version: str
    ws_openai_beta: str
    ws_service_tier: str
    ws_reasoning_effort: str
    ws_installation_id: str
    ws_tools_json: str
    ws_reconnect_limit: int
    ws_connect_timeout_seconds: int
    ws_turn_timeout_seconds: int
    oauth_reauth_retry_limit: int
    oauth_reauth_retry_delay_seconds: float
    abai_project_root: Path
    cockpit_python: Path
    oauth_mailbox_provider: str
    oauth_browser_mode: str
    oauth_browser_timeout_seconds: int


def get_settings() -> Settings:
    if load_dotenv:
        load_dotenv()
    profile_dir = os.getenv("DESKTOP_PROFILE_DIR", "").strip()
    app_user_data_dir = os.getenv("DESKTOP_APP_USER_DATA_DIR", "").strip()
    default_abai_root = Path(__file__).resolve().parents[1].parent / "aBaiAutoplus_syunnrai"
    abai_root = Path(os.getenv("ABAI_PROJECT_ROOT", str(default_abai_root)))
    default_cockpit_python = abai_root / ".venv" / "Scripts" / "python.exe"
    return Settings(
        database_path=Path(os.getenv("DATABASE_PATH", "./data/fulfillment.sqlite3")),
        low_stock_threshold=int(os.getenv("LOW_STOCK_THRESHOLD", "5")),
        max_reset_count=int(os.getenv("MAX_RESET_COUNT", "0")),
        cpa_platform=os.getenv("CPA_PLATFORM", "chatgpt"),
        cockpit_base_url=os.getenv("COCKPIT_BASE_URL", "").rstrip("/"),
        cockpit_api_token=os.getenv("COCKPIT_API_TOKEN", ""),
        xianyu_base_url=os.getenv("XIANYU_BASE_URL", "").rstrip("/"),
        xianyu_api_token=os.getenv("XIANYU_API_TOKEN", ""),
        codex_command=os.getenv("CODEX_COMMAND", "codex"),
        codex_timeout_seconds=int(os.getenv("CODEX_TIMEOUT_SECONDS", "45")),
        dry_run=_bool(os.getenv("DRY_RUN"), True),
        activation_provider=os.getenv("ACTIVATION_PROVIDER", "desktop").strip().lower() or "desktop",
        cockpit_state_dir=Path(os.getenv("COCKPIT_STATE_DIR", str(Path.home() / ".antigravity_cockpit"))),
        desktop_instance_id=os.getenv("DESKTOP_INSTANCE_ID", "").strip(),
        desktop_instance_name=os.getenv("DESKTOP_INSTANCE_NAME", "fixed-desktop-instance").strip() or "fixed-desktop-instance",
        desktop_profile_dir=Path(profile_dir) if profile_dir else None,
        desktop_app_user_data_dir=Path(app_user_data_dir) if app_user_data_dir else None,
        desktop_launch_command=os.getenv("DESKTOP_LAUNCH_COMMAND", "").strip(),
        activation_poll_seconds=float(os.getenv("ACTIVATION_POLL_SECONDS", "0.5")),
        desktop_start_timeout_seconds=int(os.getenv("DESKTOP_START_TIMEOUT_SECONDS", "60")),
        desktop_response_timeout_seconds=int(os.getenv("DESKTOP_RESPONSE_TIMEOUT_SECONDS", "180")),
        desktop_retry_limit=int(os.getenv("DESKTOP_RETRY_LIMIT", "1")),
        desktop_idle_timeout_seconds=int(os.getenv("DESKTOP_IDLE_TIMEOUT_SECONDS", "600")),
        desktop_autoclose=_bool(os.getenv("DESKTOP_AUTOCLOSE"), True),
        desktop_require_account_verification=_bool(os.getenv("DESKTOP_REQUIRE_ACCOUNT_VERIFICATION"), True),
        desktop_instance_pool=os.getenv("DESKTOP_INSTANCE_POOL", "").strip(),
        activation_worker_count=max(1, int(os.getenv("ACTIVATION_WORKER_COUNT", "3"))),
        desktop_background_mode=_bool(os.getenv("DESKTOP_BACKGROUND_MODE"), False),
        desktop_allow_foreground_fallback=_bool(os.getenv("DESKTOP_ALLOW_FOREGROUND_FALLBACK"), False),
        ws_base_url=os.getenv("WS_BASE_URL", "https://chatgpt.com/backend-api/codex").strip(),
        ws_proxy_url=os.getenv("WS_PROXY_URL", "").strip(),
        ws_model=os.getenv("WS_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna",
        ws_originator=os.getenv("WS_ORIGINATOR", "Codex Desktop").strip(),
        ws_client_version=os.getenv("WS_CLIENT_VERSION", "0.147.0-alpha.6.6").strip(),
        ws_openai_beta=os.getenv("WS_OPENAI_BETA", "responses_websockets=2026-02-06").strip(),
        ws_service_tier=os.getenv("WS_SERVICE_TIER", "priority").strip(),
        ws_reasoning_effort=os.getenv("WS_REASONING_EFFORT", "medium").strip(),
        ws_installation_id=os.getenv("WS_INSTALLATION_ID", "").strip(),
        ws_tools_json=os.getenv("WS_TOOLS_JSON", "").strip(),
        ws_reconnect_limit=max(1, int(os.getenv("WS_RECONNECT_LIMIT", "5"))),
        ws_connect_timeout_seconds=max(1, int(os.getenv("WS_CONNECT_TIMEOUT_SECONDS", "15"))),
        ws_turn_timeout_seconds=max(10, int(os.getenv("WS_TURN_TIMEOUT_SECONDS", "180"))),
        oauth_reauth_retry_limit=max(1, int(os.getenv("OAUTH_REAUTH_RETRY_LIMIT", "3"))),
        oauth_reauth_retry_delay_seconds=max(0.0, float(os.getenv("OAUTH_REAUTH_RETRY_DELAY_SECONDS", "2"))),
        abai_project_root=abai_root,
        cockpit_python=Path(os.getenv("COCKPIT_PYTHON", str(default_cockpit_python))),
        oauth_mailbox_provider=os.getenv("OAUTH_MAILBOX_PROVIDER", "cfworker_admin_api").strip() or "cfworker_admin_api",
        oauth_browser_mode=os.getenv("OAUTH_BROWSER_MODE", "camoufox_headless").strip() or "camoufox_headless",
        oauth_browser_timeout_seconds=int(os.getenv("OAUTH_BROWSER_TIMEOUT_SECONDS", "300")),
    )
