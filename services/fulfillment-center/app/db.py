from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import get_settings


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE,
    platform TEXT NOT NULL DEFAULT 'chatgpt',
    email TEXT NOT NULL DEFAULT '',
    account_id TEXT NOT NULL DEFAULT '',
    password TEXT NOT NULL DEFAULT '',
    primary_token TEXT NOT NULL DEFAULT '',
    id_token TEXT NOT NULL DEFAULT '',
    session_token TEXT NOT NULL DEFAULT '',
    refresh_token TEXT NOT NULL DEFAULT '',
    cookies TEXT NOT NULL DEFAULT '',
    lifecycle_status TEXT NOT NULL DEFAULT 'registered',
    validity_status TEXT NOT NULL DEFAULT 'unknown',
    display_status TEXT NOT NULL DEFAULT 'registered',
    token_revoked INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT NOT NULL DEFAULT '',
    reset_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'available',
    source_payload TEXT NOT NULL DEFAULT '{}',
    reserved_order_id TEXT NOT NULL DEFAULT '',
    shipped_at TEXT,
    activated_at TEXT,
    activation_error TEXT NOT NULL DEFAULT '',
    codex_reply TEXT NOT NULL DEFAULT '',
    consumed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_inventory_status ON inventory_items(status, platform);
CREATE INDEX IF NOT EXISTS idx_inventory_order ON inventory_items(reserved_order_id);

CREATE TABLE IF NOT EXISTS fulfillments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL UNIQUE,
    buyer_id TEXT NOT NULL DEFAULT '',
    chat_id TEXT NOT NULL DEFAULT '',
    account_id TEXT NOT NULL DEFAULT '',
    item_id TEXT NOT NULL DEFAULT '',
    quantity INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'created',
    inventory_id INTEGER,
    delivery_text TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    codex_reply TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(inventory_id) REFERENCES inventory_items(id)
);

CREATE TABLE IF NOT EXISTS delivery_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL UNIQUE,
    buyer_id TEXT NOT NULL DEFAULT '',
    chat_id TEXT NOT NULL DEFAULT '',
    account_id TEXT NOT NULL DEFAULT '',
    item_id TEXT NOT NULL DEFAULT '',
    platform TEXT NOT NULL DEFAULT 'chatgpt',
    requested_quantity INTEGER NOT NULL DEFAULT 1,
    allocated_quantity INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'queued',
    send_to_xianyu INTEGER NOT NULL DEFAULT 1,
    idempotency_key TEXT NOT NULL DEFAULT '',
    delivery_text TEXT NOT NULL DEFAULT '',
    allocation_attempts INTEGER NOT NULL DEFAULT 0,
    send_attempts INTEGER NOT NULL DEFAULT 0,
    reconcile_attempt INTEGER NOT NULL DEFAULT 0,
    next_run_at TEXT,
    lease_owner TEXT NOT NULL DEFAULT '',
    lease_expires_at TEXT,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_delivery_jobs_status
    ON delivery_jobs(status, next_run_at, id);
CREATE INDEX IF NOT EXISTS idx_delivery_jobs_order
    ON delivery_jobs(order_id);

CREATE TABLE IF NOT EXISTS delivery_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    order_id TEXT NOT NULL,
    buyer_id TEXT NOT NULL DEFAULT '',
    message_text TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'queued',
    attempt INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    lease_owner TEXT NOT NULL DEFAULT '',
    lease_expires_at TEXT,
    last_error TEXT NOT NULL DEFAULT '',
    sent_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(job_id, message_text),
    FOREIGN KEY(job_id) REFERENCES delivery_jobs(id)
);
CREATE INDEX IF NOT EXISTS idx_delivery_outbox_status
    ON delivery_outbox(status, next_attempt_at, id);

CREATE TABLE IF NOT EXISTS fulfillment_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    inventory_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'shipped',
    activation_reply TEXT NOT NULL DEFAULT '',
    activation_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(order_id, inventory_id),
    FOREIGN KEY(inventory_id) REFERENCES inventory_items(id)
);
CREATE INDEX IF NOT EXISTS idx_fulfillment_items_order ON fulfillment_items(order_id);

CREATE TABLE IF NOT EXISTS activation_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    buyer_id TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'queued',
    current_stage TEXT NOT NULL DEFAULT 'queued',
    provider TEXT NOT NULL DEFAULT 'ws',
    quantity INTEGER NOT NULL DEFAULT 1,
    manual INTEGER NOT NULL DEFAULT 0,
    worker_owner TEXT NOT NULL DEFAULT '',
    lease_owner TEXT NOT NULL DEFAULT '',
    lease_expires_at TEXT,
    queued_notified_at TEXT,
    activating_notified_at TEXT,
    completed_notified_at TEXT,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    finished_at TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_activation_batches_status ON activation_batches(status, id);
CREATE INDEX IF NOT EXISTS idx_activation_batches_order ON activation_batches(order_id, created_at);

CREATE TABLE IF NOT EXISTS activation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    order_id TEXT NOT NULL,
    inventory_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    stage TEXT NOT NULL DEFAULT 'queued',
    provider TEXT NOT NULL DEFAULT 'ws',
    attempt INTEGER NOT NULL DEFAULT 0,
    lease_owner TEXT NOT NULL DEFAULT '',
    lease_expires_at TEXT,
    reply_preview TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(batch_id, inventory_id),
    FOREIGN KEY(batch_id) REFERENCES activation_batches(id),
    FOREIGN KEY(inventory_id) REFERENCES inventory_items(id)
);
CREATE INDEX IF NOT EXISTS idx_activation_jobs_batch ON activation_jobs(batch_id, id);
CREATE INDEX IF NOT EXISTS idx_activation_jobs_status ON activation_jobs(status, id);
CREATE TABLE IF NOT EXISTS activation_worker_locks (
    name TEXT PRIMARY KEY,
    owner TEXT NOT NULL DEFAULT '',
    lease_expires_at TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS oauth_reauth_sessions (
    id TEXT PRIMARY KEY,
    inventory_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    state TEXT NOT NULL UNIQUE,
    code_verifier TEXT NOT NULL,
    client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    auth_url TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(inventory_id) REFERENCES inventory_items(id)
);
CREATE INDEX IF NOT EXISTS idx_oauth_reauth_inventory ON oauth_reauth_sessions(inventory_id, created_at);

CREATE TABLE IF NOT EXISTS oauth_refresh_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL DEFAULT 'queued',
    total INTEGER NOT NULL DEFAULT 0,
    queued INTEGER NOT NULL DEFAULT 0,
    succeeded INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    cancelled INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_oauth_refresh_batches_status
    ON oauth_refresh_batches(status, id);

CREATE TABLE IF NOT EXISTS oauth_refresh_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    inventory_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempt INTEGER NOT NULL DEFAULT 0,
    lease_owner TEXT NOT NULL DEFAULT '',
    lease_expires_at TEXT,
    last_error TEXT NOT NULL DEFAULT '',
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(batch_id, inventory_id),
    FOREIGN KEY(batch_id) REFERENCES oauth_refresh_batches(id),
    FOREIGN KEY(inventory_id) REFERENCES inventory_items(id)
);
CREATE INDEX IF NOT EXISTS idx_oauth_refresh_jobs_status
    ON oauth_refresh_jobs(status, id);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL DEFAULT '',
    inventory_id INTEGER,
    event_type TEXT NOT NULL,
    idempotency_key TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_order ON audit_events(order_id, created_at);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    scope TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    acknowledged INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


DEFAULT_SETTINGS = {
    "delivery_template": "请把下面这个邮箱复制到您的 Codex 邀请界面发送。发送成功后，请立刻回复我【已邀请】三个字。\\n\\n{accounts}\\n\\n收到您的回复后，我这边会立刻为您激活；稍微等待几分钟，您就会收到激活成功的提示。",
    "xianyu_send_endpoint": "/internal/accounts/{account_id}/send-message",
    "xianyu_account_id": "",
    "xianyu_base_url": "",
    "xianyu_api_token": "",
    "cockpit_base_url": "",
    "cockpit_api_token": "",
    "codex_command": "codex",
    "codex_prompt": "你好",
    "activation_provider": "ws",
    "desktop_instance_name": "fixed-desktop-instance",
    "desktop_instance_id": "",
    "desktop_profile_dir": "",
    "desktop_app_user_data_dir": "",
    "desktop_launch_command": "",
    "desktop_instance_pool": "",
    "activation_worker_count": "1",
    "desktop_background_mode": "false",
    "oauth_reauth_retry_limit": "3",
    "oauth_reauth_retry_delay_seconds": "2",
    "delivery_worker_count": "1",
    "delivery_retry_limit": "5",
    "oauth_reauth_retry_delays": "2,5,10",
    "delivery_retry_base_seconds": "1",
    "delivery_quantity_reconcile_delays": "0.5,1,2",
    "desktop_allow_foreground_fallback": "false",
    "ws_base_url": "",
    "ws_proxy_url": "",
    "ws_model": "gpt-5.6-luna",
    "ws_originator": "Codex Desktop",
    "ws_client_version": "0.147.0-alpha.6.6",
    "ws_openai_beta": "responses_websockets=2026-02-06",
    "ws_service_tier": "priority",
    "ws_reasoning_effort": "medium",
    "ws_installation_id": "",
    "ws_tools_json": "",
    "ws_reconnect_limit": "5",
    "ws_connect_timeout_seconds": "15",
    "ws_turn_timeout_seconds": "180",
}


def _migrate(conn: sqlite3.Connection) -> None:
    def columns(table: str) -> set[str]:
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    def add_column(table: str, column: str, ddl: str) -> None:
        if column not in columns(table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    add_column("inventory_items", "shipped_at", "TEXT")
    add_column("inventory_items", "activated_at", "TEXT")
    add_column("inventory_items", "activation_error", "TEXT NOT NULL DEFAULT ''")
    add_column("inventory_items", "codex_reply", "TEXT NOT NULL DEFAULT ''")
    add_column("inventory_items", "account_id", "TEXT NOT NULL DEFAULT ''")
    add_column("inventory_items", "id_token", "TEXT NOT NULL DEFAULT ''")
    add_column("inventory_items", "expires_at", "TEXT NOT NULL DEFAULT ''")
    add_column("fulfillments", "quantity", "INTEGER NOT NULL DEFAULT 1")
    add_column("fulfillments", "chat_id", "TEXT NOT NULL DEFAULT ''")
    add_column("fulfillments", "account_id", "TEXT NOT NULL DEFAULT ''")
    add_column("delivery_jobs", "chat_id", "TEXT NOT NULL DEFAULT ''")
    add_column("delivery_jobs", "account_id", "TEXT NOT NULL DEFAULT ''")
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO app_settings(key, value) VALUES (?, ?)",
            (key, value),
        )


_INIT_LOCK = threading.Lock()
_INITIALIZED_DATABASES: set[str] = set()


def init_db() -> None:
    settings = get_settings()
    database_path = Path(settings.database_path).resolve()
    database_key = str(database_path).lower()
    if database_key in _INITIALIZED_DATABASES:
        return
    with _INIT_LOCK:
        if database_key in _INITIALIZED_DATABASES:
            return
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as conn:
            conn.row_factory = sqlite3.Row
            conn.executescript(SCHEMA)
            _migrate(conn)
            conn.commit()
        _INITIALIZED_DATABASES.add(database_key)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    init_db()
    settings = get_settings()
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
