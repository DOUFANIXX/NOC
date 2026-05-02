from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import current_app, g


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    ui_preference TEXT NOT NULL DEFAULT 'dark',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor TEXT NOT NULL,
    mac TEXT NOT NULL,
    username TEXT,
    device_type TEXT,
    firmware TEXT,
    ip TEXT,
    rssi TEXT,
    sector_name TEXT,
    sector_ip TEXT,
    source_ip TEXT,
    raw_json TEXT,
    last_seen_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(vendor, mac)
);

CREATE TABLE IF NOT EXISTS switch_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_type TEXT NOT NULL,
    city TEXT,
    area TEXT,
    site TEXT,
    name TEXT NOT NULL,
    ip TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(inventory_type, ip)
);

CREATE TABLE IF NOT EXISTS sector_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor TEXT NOT NULL,
    sector_ip TEXT NOT NULL,
    sector_name TEXT,
    source_detail TEXT,
    last_seen_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(vendor, sector_ip)
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,
    vendor TEXT,
    trigger_source TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_by INTEGER,
    message TEXT,
    meta_json TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS scan_schedules (
    vendor TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    daily_time TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    actor_username TEXT,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    details_json TEXT,
    remote_addr TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_devices_vendor ON devices(vendor);
CREATE INDEX IF NOT EXISTS idx_jobs_vendor_status ON jobs(vendor, status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
"""


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def get_db() -> sqlite3.Connection:
    connection = g.get("_db")
    if connection is None:
        db_path = Path(current_app.config["DATABASE_PATH"])
        _ensure_parent(db_path)
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        g._db = connection
    return connection


def close_db(_error=None) -> None:
    connection = g.pop("_db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    db = get_db()
    db.executescript(SCHEMA)
    _ensure_user_columns(db)
    db.commit()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)


def _ensure_user_columns(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "ui_preference" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN ui_preference TEXT NOT NULL DEFAULT 'dark'")
