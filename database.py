import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "sqls.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sqls (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    week        INTEGER,
    month       TEXT,
    year        INTEGER,
    state       TEXT,
    lead_source TEXT,
    sql_count   REAL DEFAULT 1.0,
    synced_at   TEXT
);
CREATE TABLE IF NOT EXISTS sync_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    synced_at TEXT NOT NULL,
    new_deals INTEGER,
    source    TEXT
);
"""


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(_SCHEMA)


def upsert_deal(conn, row: dict):
    conn.execute(
        """
        INSERT INTO sqls (id, created_at, week, month, year, state, lead_source, sql_count, synced_at)
        VALUES (:id, :created_at, :week, :month, :year, :state, :lead_source, :sql_count, :synced_at)
        ON CONFLICT(id) DO UPDATE SET
            created_at  = excluded.created_at,
            week        = excluded.week,
            month       = excluded.month,
            year        = excluded.year,
            state       = excluded.state,
            lead_source = excluded.lead_source,
            synced_at   = excluded.synced_at
        """,
        row,
    )


def get_existing_ids(conn) -> set:
    return {r["id"] for r in conn.execute("SELECT id FROM sqls").fetchall()}


def get_all_deals(conn) -> list:
    return [dict(r) for r in conn.execute("SELECT * FROM sqls ORDER BY created_at").fetchall()]


def log_sync(conn, new_deals: int, source: str):
    conn.execute(
        "INSERT INTO sync_log (synced_at, new_deals, source) VALUES (?, ?, ?)",
        (datetime.utcnow().isoformat(), new_deals, source),
    )


def get_last_sync(conn) -> dict | None:
    row = conn.execute(
        "SELECT * FROM sync_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None
