"""
gui/components/structure/registry/custom_material_db.py

SQLite-backed store for user-created custom material databases.
Multiple logical databases live in a single file, distinguished by
the db_name column (e.g. "biharSOR-2026", "My Materials").
"""

import sqlite3
import datetime
from pathlib import Path

# Resolve to <project_root>/data/user.db regardless of where this file lives.
# __file__ is  gui/components/structure/registry/custom_material_db.py
# .parents[4] → registry(0) → structure(1) → components(2) → gui(3) → root(4)
_DB_PATH = Path(__file__).parents[4] / "data" / "user.db"
CUSTOM_PREFIX = "custom::"


class CustomMaterialDB:
    """
    Thin wrapper around a single SQLite file that stores custom SOR-style
    materials.  Each 'logical database' the user creates is just a distinct
    value in the db_name column - no separate files needed.
    """

    def __init__(self, path: Path = _DB_PATH):
        self._path = path
        self._ensure_schema()

    # ── Internal ──────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS custom_materials (
                    id                               INTEGER PRIMARY KEY AUTOINCREMENT,
                    db_name                          TEXT    NOT NULL,
                    name                             TEXT    NOT NULL,
                    unit                             TEXT,
                    rate                             REAL,
                    rate_src                         TEXT,
                    carbon_emission                  TEXT,
                    carbon_emission_units_den        TEXT,
                    carbon_emission_src              TEXT,
                    conversion_factor                TEXT,
                    scrap_rate                       TEXT,
                    post_demolition_recovery_pct     TEXT,
                    recycleable                      TEXT,
                    material_type                    TEXT,
                    grade                            TEXT,
                    created_at                       TEXT DEFAULT (datetime('now')),
                    updated_at                       TEXT DEFAULT (datetime('now'))
                )
            """)
            # Migrate existing databases that pre-date the fuller schema
            for col, typedef in (
                ("carbon_emission_src",          "TEXT"),
                ("scrap_rate",                   "TEXT"),
                ("post_demolition_recovery_pct", "TEXT"),
            ):
                try:
                    conn.execute(f"ALTER TABLE custom_materials ADD COLUMN {col} {typedef}")
                except Exception:
                    pass  # column already exists
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_db_name "
                "ON custom_materials(db_name)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS custom_units (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol     TEXT    NOT NULL UNIQUE,
                    name       TEXT,
                    dimension  TEXT    NOT NULL,
                    to_si      REAL    NOT NULL,
                    si_unit    TEXT    NOT NULL,
                    created_at TEXT    DEFAULT (datetime('now'))
                )
            """)

    # ── Queries ───────────────────────────────────────────────────────────

    def list_db_names(self) -> list:
        """Return all distinct custom database names, sorted."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT db_name FROM custom_materials ORDER BY db_name"
            ).fetchall()
        return [r["db_name"] for r in rows]

    def get_items(self, db_name: str) -> list:
        """Return all materials in *db_name* as SOR-compatible item dicts."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT name, unit, rate, rate_src,
                       carbon_emission, carbon_emission_units_den, carbon_emission_src,
                       conversion_factor, scrap_rate, post_demolition_recovery_pct,
                       recycleable, material_type, grade
                FROM   custom_materials
                WHERE  db_name = ?
                ORDER  BY name
                """,
                (db_name,),
            ).fetchall()
        db_key = f"{CUSTOM_PREFIX}{db_name}"
        return [
            {
                "name":                           r["name"],
                "unit":                           r["unit"] or "",
                "rate":                           r["rate"] if r["rate"] is not None else None,
                "rate_src":                       r["rate_src"] or "",
                "carbon_emission":                r["carbon_emission"] or None,
                "carbon_emission_units_den":      r["carbon_emission_units_den"] or None,
                "carbon_emission_src":            r["carbon_emission_src"] or "",
                "conversion_factor":              r["conversion_factor"] or None,
                "scrap_rate":                     r["scrap_rate"] or "",
                "post_demolition_recovery_pct":   r["post_demolition_recovery_pct"] or "",
                "recycleable":                    r["recycleable"] or "",
                "type":                           r["material_type"] or "",
                "grade":                          r["grade"] or "",
                "db_key":                         db_key,
            }
            for r in rows
        ]

    # ── Mutations ─────────────────────────────────────────────────────────

    def save_material(self, db_name: str, mat_dict: dict):
        """
        Insert or update a material in *db_name*.
        *mat_dict* is the structured dict returned by MaterialDialog.get_values()
        ({values, meta, state}).
        Existing row with the same (db_name, name) is updated in-place.
        """
        now = datetime.datetime.now().isoformat()
        v = mat_dict.get("values", {})

        name = (v.get("material_name") or "").strip()
        if not name:
            raise ValueError("material_name must not be empty")

        carbon_unit = v.get("carbon_unit") or ""
        denom = carbon_unit.split("/")[-1].strip() if "/" in carbon_unit else ""

        carbon_em = v.get("carbon_emission", None)
        carbon_em_str = str(carbon_em) if carbon_em else None

        cf = v.get("conversion_factor", None)
        cf_str = str(cf) if cf else None

        scrap = v.get("scrap_rate", None)
        scrap_str = str(scrap) if scrap else ""

        recovery = v.get("post_demolition_recovery_percentage", None)
        recovery_str = str(recovery) if recovery else ""

        recycleable = "Recyclable" if v.get("is_recyclable") else "Non-recyclable"

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM custom_materials WHERE db_name=? AND name=?",
                (db_name, name),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE custom_materials SET
                        unit=?, rate=?, rate_src=?,
                        carbon_emission=?, carbon_emission_units_den=?, carbon_emission_src=?,
                        conversion_factor=?, scrap_rate=?, post_demolition_recovery_pct=?,
                        recycleable=?, material_type=?, grade=?, updated_at=?
                    WHERE db_name=? AND name=?
                    """,
                    (
                        v.get("unit", ""),
                        v.get("rate") or None,
                        v.get("rate_source", ""),
                        carbon_em_str, denom,
                        v.get("carbon_emission_src", ""),
                        cf_str, scrap_str, recovery_str, recycleable,
                        v.get("type", ""), v.get("grade", ""),
                        now, db_name, name,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO custom_materials
                        (db_name, name, unit, rate, rate_src,
                         carbon_emission, carbon_emission_units_den, carbon_emission_src,
                         conversion_factor, scrap_rate, post_demolition_recovery_pct,
                         recycleable, material_type, grade, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        db_name, name,
                        v.get("unit", ""),
                        v.get("rate") or None,
                        v.get("rate_source", ""),
                        carbon_em_str, denom,
                        v.get("carbon_emission_src", ""),
                        cf_str, scrap_str, recovery_str, recycleable,
                        v.get("type", ""), v.get("grade", ""),
                        now, now,
                    ),
                )

    def delete_material(self, db_name: str, name: str):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM custom_materials WHERE db_name=? AND name=?",
                (db_name, name),
            )

    def delete_db(self, db_name: str):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM custom_materials WHERE db_name=?",
                (db_name,),
            )

    # ── Custom Units ──────────────────────────────────────────────────────

    def list_custom_units(self) -> list:
        """Return all user-defined custom units as dicts."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT symbol, name, dimension, to_si, si_unit "
                "FROM custom_units ORDER BY symbol"
            ).fetchall()
        return [
            {
                "symbol":    r["symbol"],
                "name":      r["name"] or "",
                "dimension": r["dimension"],
                "to_si":     r["to_si"],
                "si_unit":   r["si_unit"],
            }
            for r in rows
        ]

    def save_custom_unit(self, unit: dict):
        """Insert or replace a custom unit (keyed by symbol)."""
        symbol = (unit.get("symbol") or "").strip()
        if not symbol:
            raise ValueError("symbol must not be empty")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO custom_units (symbol, name, dimension, to_si, si_unit)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name      = excluded.name,
                    dimension = excluded.dimension,
                    to_si     = excluded.to_si,
                    si_unit   = excluded.si_unit
                """,
                (
                    symbol,
                    unit.get("name", ""),
                    unit.get("dimension", ""),
                    float(unit.get("to_si", 1.0)),
                    unit.get("si_unit", ""),
                ),
            )

    def delete_custom_unit(self, symbol: str):
        """Delete a custom unit by symbol."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM custom_units WHERE symbol=?", (symbol,)
            )


