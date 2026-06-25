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


def get_settings() -> Settings:
    if load_dotenv:
        load_dotenv()
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
    )

