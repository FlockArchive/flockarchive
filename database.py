import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_PATH


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                added_at TEXT NOT NULL,
                is_seed INTEGER NOT NULL DEFAULT 0
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_id INTEGER NOT NULL,
                captured_at TEXT NOT NULL,
                html_path TEXT,
                screenshot_path TEXT,
                html_hash TEXT,
                changed INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                FOREIGN KEY (url_id) REFERENCES urls(id)
            )
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_url_id
            ON snapshots(url_id, captured_at DESC)
        """)


@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_url(url: str, is_seed: bool = False) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            "INSERT OR IGNORE INTO urls (url, added_at, is_seed) VALUES (?, ?, ?)",
            (url, now, int(is_seed)),
        )
        row = db.execute("SELECT id FROM urls WHERE url = ?", (url,)).fetchone()
        return row["id"]


def get_all_urls():
    with get_db() as db:
        return db.execute("SELECT * FROM urls ORDER BY added_at DESC").fetchall()


def get_url_by_id(url_id: int):
    with get_db() as db:
        return db.execute("SELECT * FROM urls WHERE id = ?", (url_id,)).fetchone()


def add_snapshot(url_id: int, html_path: str | None, screenshot_path: str | None,
                 html_hash: str, changed: bool, error: str | None = None) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO snapshots
               (url_id, captured_at, html_path, screenshot_path, html_hash, changed, error)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (url_id, now, html_path, screenshot_path, html_hash, int(changed), error),
        )
        return cursor.lastrowid


def get_snapshots_for_url(url_id: int):
    with get_db() as db:
        return db.execute(
            "SELECT * FROM snapshots WHERE url_id = ? ORDER BY captured_at DESC",
            (url_id,),
        ).fetchall()


def get_latest_snapshot(url_id: int):
    with get_db() as db:
        return db.execute(
            "SELECT * FROM snapshots WHERE url_id = ? ORDER BY captured_at DESC LIMIT 1",
            (url_id,),
        ).fetchone()



def get_snapshot_by_id(snapshot_id: int):
    with get_db() as db:
        return db.execute("""
            SELECT s.*, u.url
            FROM snapshots s
            JOIN urls u ON s.url_id = u.id
            WHERE s.id = ?
        """, (snapshot_id,)).fetchone()


def get_recent_snapshots(limit: int = 100):
    with get_db() as db:
        return db.execute("""
            SELECT s.*, u.url
            FROM snapshots s
            JOIN urls u ON s.url_id = u.id
            ORDER BY s.captured_at DESC
            LIMIT ?
        """, (limit,)).fetchall()


def search_urls(query: str):
    with get_db() as db:
        return db.execute(
            "SELECT * FROM urls WHERE url LIKE ? ORDER BY added_at DESC",
            (f"%{query}%",),
        ).fetchall()


def get_stats() -> dict:
    with get_db() as db:
        row = db.execute("""
            SELECT
                (SELECT COUNT(*) FROM urls) as url_count,
                (SELECT COUNT(*) FROM snapshots) as snapshot_count,
                (SELECT COUNT(*) FROM snapshots WHERE changed = 1) as changed_count
        """).fetchone()
        return dict(row)
