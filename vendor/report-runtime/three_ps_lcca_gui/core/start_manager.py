"""
core/start_manager.py

Manages user-level home page data in data/user.db.
Tables: user_profile, pinned_projects, recent_projects, home_preferences
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from three_ps_lcca_gui.core.safechunk_engine import SafeChunkEngine

# ── Paths ──────────────────────────────────────────────────────────────────────
def _get_db_path() -> str:
    """Returns the DB path, resolved at runtime to ensure SafeChunkEngine is configured."""
    base_dir = Path(SafeChunkEngine.get_default_base_dir()).parent
    db_path = os.path.join(base_dir, "data", "user.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return db_path


_RECENT_LIMIT = 15


def _now() -> str:
    return datetime.now().isoformat()


def _conn() -> sqlite3.Connection:
    path = _get_db_path()
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    return c


def _ensure_tables():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id          INTEGER PRIMARY KEY DEFAULT 1,
                display_name TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS pinned_projects (
                project_id  TEXT PRIMARY KEY,
                pinned_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS recent_projects (
                project_id      TEXT PRIMARY KEY,
                last_opened_at  TEXT NOT NULL DEFAULT (datetime('now')),
                open_count      INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS home_preferences (
                key         TEXT PRIMARY KEY,
                value       TEXT,
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS comparison_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                compared_at     TEXT NOT NULL DEFAULT (datetime('now')),
                label           TEXT NOT NULL,
                project_ids     TEXT NOT NULL,
                project_names   TEXT NOT NULL,
                analysis_period INTEGER NOT NULL DEFAULT 0
            );
        """)


# ── Bootstrap ──────────────────────────────────────────────────────────────────

_ensure_tables()


# ── User profile ──────────────────────────────────────────────────────────────

def get_profile() -> dict:
    with _conn() as c:
        row = c.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
        if row:
            return dict(row)
        return {}


def is_first_launch() -> bool:
    return not bool(get_profile())


def set_name(name: str):
    now = _now()
    with _conn() as c:
        c.execute("""
            INSERT INTO user_profile (id, display_name, created_at, updated_at)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET display_name = excluded.display_name,
                                          updated_at   = excluded.updated_at
        """, (name.strip(), now, now))


# ── Recent projects ────────────────────────────────────────────────────────────

def record_open(project_id: str):
    now = _now()
    with _conn() as c:
        c.execute("""
            INSERT INTO recent_projects (project_id, last_opened_at, open_count)
            VALUES (?, ?, 1)
            ON CONFLICT(project_id) DO UPDATE
                SET last_opened_at = excluded.last_opened_at,
                    open_count     = open_count + 1
        """, (project_id, now))
        # Prune to RECENT_LIMIT
        c.execute("""
            DELETE FROM recent_projects WHERE project_id NOT IN (
                SELECT project_id FROM recent_projects
                ORDER BY last_opened_at DESC LIMIT ?
            )
        """, (_RECENT_LIMIT,))


def get_recent(limit: int = _RECENT_LIMIT) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT project_id, last_opened_at, open_count
            FROM recent_projects
            ORDER BY last_opened_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


# ── Pinned projects ────────────────────────────────────────────────────────────

def pin(project_id: str):
    with _conn() as c:
        c.execute("""
            INSERT OR IGNORE INTO pinned_projects (project_id, pinned_at)
            VALUES (?, ?)
        """, (project_id, _now()))


def unpin(project_id: str):
    with _conn() as c:
        c.execute("DELETE FROM pinned_projects WHERE project_id = ?", (project_id,))


def is_pinned(project_id: str) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM pinned_projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        return row is not None


def get_pinned() -> list[str]:
    with _conn() as c:
        rows = c.execute(
            "SELECT project_id FROM pinned_projects ORDER BY pinned_at DESC"
        ).fetchall()
        return [r["project_id"] for r in rows]


# ── Home preferences ───────────────────────────────────────────────────────────

def get_pref(key: str, default: str = "") -> str:
    with _conn() as c:
        row = c.execute(
            "SELECT value FROM home_preferences WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_pref(key: str, value: str):
    with _conn() as c:
        c.execute("""
            INSERT INTO home_preferences (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                           updated_at = excluded.updated_at
        """, (key, value, _now()))


# ── Comparison history ─────────────────────────────────────────────────────────

def add_comparison(label: str, project_ids: list, project_names: list,
                   analysis_period: int = 0) -> int:
    """Record a confirmed comparison group. Returns the new row id."""
    with _conn() as c:
        cur = c.execute("""
            INSERT INTO comparison_history
                (compared_at, label, project_ids, project_names, analysis_period)
            VALUES (?, ?, ?, ?, ?)
        """, (_now(), label,
              json.dumps(project_ids), json.dumps(project_names),
              analysis_period))
        return cur.lastrowid


def get_comparison_history(limit: int = 100) -> list[dict]:
    """Return comparison history rows newest-first, with decoded JSON fields."""
    with _conn() as c:
        rows = c.execute("""
            SELECT id, compared_at, label, project_ids, project_names, analysis_period
            FROM comparison_history
            ORDER BY compared_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["project_ids"]   = json.loads(d["project_ids"])
        d["project_names"] = json.loads(d["project_names"])
        result.append(d)
    return result


def delete_comparison(history_id: int):
    """Remove a comparison history row by id."""
    with _conn() as c:
        c.execute("DELETE FROM comparison_history WHERE id = ?", (history_id,))


def delete_all_comparisons():
    """Clear the entire comparison history table."""
    with _conn() as c:
        c.execute("DELETE FROM comparison_history")