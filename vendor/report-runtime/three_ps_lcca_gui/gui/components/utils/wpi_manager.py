"""
utils/wpi_manager.py

WPIProfile dataclass and WPIManager for loading, verifying,
and managing WPI adjustment ratio profiles.

Integrity states:
    OK          - hash verified
    MISMATCH    - data tampered, entry unlisted
    MISSING     - no hash stored, entry unlisted
"""

from __future__ import annotations

import json
import sqlite3
import uuid
import datetime
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional
from .wpi_hash import compute_hash, verify_hash

# ── User DB path ──────────────────────────────────────────────────────────────
# Single SQLite file shared across all projects (same folder as wpi_db.json).
_USER_DB_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "user.db"
)


# ── Integrity State ───────────────────────────────────────────────────────────


class IntegrityState(Enum):
    OK = auto()        # hash verified
    MISMATCH = auto()  # data tampered → unlist
    MISSING = auto()   # no hash stored → unlist


# ── WPI Data structure keys ───────────────────────────────────────────────────

VEHICLES = [
    "small_cars",
    "big_cars",
    "two_wheelers",
    "o_buses",
    "d_buses",
    "lcv",
    "hcv",
    "mcv",
]

COST_KEYS = [
    "petrol", "diesel", "engine_oil", "other_oil", "grease",
    "property_damage", "tyre_cost", "spare_parts", "fixed_depreciation",
    "commodity_holding_cost",
    "passenger_cost", "crew_cost",
    "fatal", "major", "minor",
    "vot_cost",
]


def empty_data() -> dict:
    """Return a WPI data block with all values set to 1.0 (no adjustment)."""
    return {v: {k: 1.0 for k in COST_KEYS} for v in VEHICLES}


# ── WPIProfile ────────────────────────────────────────────────────────────────


@dataclass
class WPIProfile:
    id: str
    name: str
    year: int
    is_custom: bool
    remark: str
    hash: str
    data: dict
    is_shared: bool = False
    integrity: IntegrityState = field(default=IntegrityState.MISSING, init=False)

    def __post_init__(self):
        self._check_integrity()

    def _check_integrity(self):
        if not self.hash:
            self.integrity = IntegrityState.MISSING
        elif verify_hash(self.data, self.hash):
            self.integrity = IntegrityState.OK
        else:
            self.integrity = IntegrityState.MISMATCH

    def is_listed(self) -> bool:
        """DB entries must pass integrity. Custom entries always listed."""
        if self.is_custom:
            return True
        return self.integrity == IntegrityState.OK

    def to_dict(self) -> dict:
        """Serialize back to JSON-compatible dict."""
        return {
            "metadata": {
                "id": self.id,
                "name": self.name,
                "year": self.year,
                "is_custom": self.is_custom,
                "remark": self.remark,
                "hash": self.hash,
                "is_shared": self.is_shared,
            },
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WPIProfile":
        m = d["metadata"]
        return cls(
            id=m["id"],
            name=m["name"],
            year=m.get("year", 0),
            is_custom=m.get("is_custom", True),
            remark=m.get("remark", ""),
            hash=m.get("hash", ""),
            is_shared=m.get("is_shared", False),
            data=d["data"],
        )

    def make_custom_copy(self, new_name: str) -> "WPIProfile":
        """Clone this profile as a new custom entry with a fresh id."""
        copy = WPIProfile(
            id=f"wpi_custom_{uuid.uuid4().hex[:8]}",
            name=new_name,
            year=self.year,
            is_custom=True,
            remark=f"Derived from '{self.name}'",
            hash="",
            data=json.loads(json.dumps(self.data)),  # deep copy
            is_shared=self.is_shared,
        )
        copy.stamp_hash()
        return copy

    def stamp_hash(self):
        """Compute and store hash from current data (for custom profiles)."""
        self.hash = compute_hash(self.data)
        self.integrity = IntegrityState.OK


# ── WPIManager ────────────────────────────────────────────────────────────────


class WPIManager:
    """
    Manages DB and custom WPI profiles.

    DB profiles are loaded from wpi_db.json (read-only, hash-verified).
    Custom profiles are stored per-project (passed in as a list of dicts).
    """

    def __init__(self, db_path: Path):
        self._db_profiles: list[WPIProfile] = []
        self._custom_profiles: list[WPIProfile] = []
        self._unlisted: list[WPIProfile] = []  # failed integrity
        self._load_db(db_path)

    # ── DB loading ────────────────────────────────────────────────────────────

    def _load_db(self, db_path: Path):
        if not db_path.exists():
            raise FileNotFoundError(f"WPI DB not found: {db_path}")

        with open(db_path, "r", encoding="utf-8") as f:
            db = json.load(f)

        for entry in db.get("entries", []):
            profile = WPIProfile.from_dict(entry)
            if profile.is_listed():
                self._db_profiles.append(profile)
            else:
                self._unlisted.append(profile)

    # ── Custom profile management ─────────────────────────────────────────────

    def load_custom_profiles(self, raw: list[dict]):
        """Load custom profiles from project data."""
        self._custom_profiles.clear()
        for entry in raw:
            profile = WPIProfile.from_dict(entry)
            self._custom_profiles.append(profile)

    def dump_custom_profiles(self) -> list[dict]:
        """Serialize custom profiles for saving into project."""
        return [p.to_dict() for p in self._custom_profiles]

    def add_custom(self, profile: WPIProfile):
        self._custom_profiles.append(profile)

    def delete_custom(self, profile_id: str):
        self._custom_profiles = [
            p for p in self._custom_profiles if p.id != profile_id
        ]

    def save_custom(self, profile: WPIProfile):
        """Update existing custom profile in place."""
        profile.stamp_hash()
        for i, p in enumerate(self._custom_profiles):
            if p.id == profile.id:
                self._custom_profiles[i] = profile
                return
        # Not found - add as new
        self._custom_profiles.append(profile)

    # ── Queries ───────────────────────────────────────────────────────────────

    def all_listed(self) -> list[WPIProfile]:
        """All profiles available for selection (DB + custom)."""
        return self._db_profiles + self._custom_profiles

    def get_by_id(self, profile_id: str) -> Optional[WPIProfile]:
        for p in self.all_listed():
            if p.id == profile_id:
                return p
        return None

    def is_name_taken(self, name: str, exclude_id: str = "") -> bool:
        for p in self.all_listed():
            if p.id == exclude_id:
                continue
            if p.name.strip().lower() == name.strip().lower():
                return True
        return False

    def suggest_custom_name(self, base_name: str) -> str:
        """Suggest a unique name like '2024-user', '2024-user-2', etc."""
        candidate = f"{base_name}-user"
        if not self.is_name_taken(candidate):
            return candidate
        i = 2
        while self.is_name_taken(f"{candidate}-{i}"):
            i += 1
        return f"{candidate}-{i}"

    @property
    def unlisted(self) -> list[WPIProfile]:
        """Profiles that failed integrity check (for logging/warning)."""
        return self._unlisted


# ── UserWPILibrary ────────────────────────────────────────────────────────────


class UserWPILibrary:
    """
    SQLite-backed global library of WPI profiles, shared across all projects.

    Stored in data/user.db - one row per saved profile.
    """

    def __init__(self, path: Path = _USER_DB_PATH):
        self._path = path
        self._ensure_schema()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wpi_profiles (
                    id         TEXT PRIMARY KEY,
                    name       TEXT NOT NULL,
                    year       INTEGER NOT NULL,
                    remark     TEXT DEFAULT '',
                    data       TEXT NOT NULL,
                    hash       TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """)

    # ── Queries ───────────────────────────────────────────────────────────────

    def all(self) -> list[WPIProfile]:
        """Return all library profiles, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM wpi_profiles ORDER BY updated_at DESC"
            ).fetchall()
        profiles = []
        for r in rows:
            try:
                profiles.append(self._row_to_profile(r))
            except Exception:
                pass
        return profiles

    def name_exists(self, name: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM wpi_profiles WHERE LOWER(name)=LOWER(?)", (name,)
            ).fetchone()
        return row is not None

    def unique_name(self, base: str) -> str:
        """
        Return a name guaranteed to be unique in the library.
        Uses  base → base (2) → base (3) …  to stay readable.
        """
        if not self.name_exists(base):
            return base
        i = 2
        while self.name_exists(f"{base} ({i})"):
            i += 1
        return f"{base} ({i})"

    # ── Mutations ─────────────────────────────────────────────────────────────

    def save(self, profile: WPIProfile) -> None:
        """Insert or replace a profile (keyed by id)."""
        now = datetime.datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO wpi_profiles (id, name, year, remark, data, hash,
                                         created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name       = excluded.name,
                    year       = excluded.year,
                    remark     = excluded.remark,
                    data       = excluded.data,
                    hash       = excluded.hash,
                    updated_at = excluded.updated_at
                """,
                (
                    profile.id, profile.name, profile.year,
                    profile.remark, json.dumps(profile.data),
                    profile.hash, now, now,
                ),
            )

    def delete(self, profile_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM wpi_profiles WHERE id=?", (profile_id,)
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_profile(r: sqlite3.Row) -> WPIProfile:
        return WPIProfile(
            id=r["id"],
            name=r["name"],
            year=r["year"],
            is_custom=True,
            remark=r["remark"] or "",
            hash=r["hash"] or "",
            data=json.loads(r["data"]),
        )


# ── Module-level convenience ──────────────────────────────────────────────────
# A single shared instance so callers don't have to instantiate the class.

_library = UserWPILibrary()


def load_user_library() -> list[WPIProfile]:
    """Return all profiles from the global user WPI library."""
    return _library.all()


def save_to_user_library(profile: WPIProfile) -> None:
    """Add or update *profile* in the global user WPI library."""
    _library.save(profile)


def delete_from_user_library(profile_id: str) -> None:
    """Remove a profile by id from the global user WPI library."""
    _library.delete(profile_id)


def library_unique_name(base: str) -> str:
    """
    Return a name that does not clash with any existing library entry.
    e.g. 'My 2024'  →  'My 2024 (2)'  →  'My 2024 (3)'  …
    """
    return _library.unique_name(base)


