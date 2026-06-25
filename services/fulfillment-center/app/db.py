from __future__ import annotations

import sqlite3
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
    password TEXT NOT NULL DEFAULT '',
    primary_token TEXT NOT NULL DEFAULT '',
    session_token TEXT NOT NULL DEFAULT '',
    refresh_token TEXT NOT NULL DEFAULT '',
    cookies TEXT NOT NULL DEFAULT '',
    lifecycle_status TEXT NOT NULL DEFAULT 'registered',
    validity_status TEXT NOT NULL DEFAULT 'unknown',
    display_status TEXT NOT NULL DEFAULT 'registered',
    token_revoked INTEGER NOT NULL DEFAULT 0,
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
    "delivery_template": "请把下面这个邮箱复制到您的 Codex 邀请界面发送。发送成功后，请立刻回复我【已邀请】三个字。\n\n{accounts}\n\n收到您的回复后，我这边会立刻为您激活；稍微等待几分钟，您就会收到激活成功的提示。",
    "xianyu_send_endpoint": "/internal/accounts/{account_id}/send-message",
    "xianyu_account_id": "",
    "xianyu_base_url": "",
    "xianyu_api_token": "",
    "cockpit_base_url": "",
    "cockpit_api_token": "",
    "codex_command": "codex",
    "codex_prompt": "只回复：你好",
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
    add_column("fulfillments", "quantity", "INTEGER NOT NULL DEFAULT 1")
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO app_settings(key, value) VALUES (?, ?)",
            (key, value),
        )


def init_db() -> None:
    settings = get_settings()
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.database_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    init_db()
    settings = get_settings()
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
