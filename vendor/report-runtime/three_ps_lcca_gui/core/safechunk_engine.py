"""
SafeChunkEngine v3.0

Project structure:
  chunks/x.lcca              - current save
  chunks_bak/x.lcca.bak      - previous save
  chunks_bak/x.lcca.ebak     - one before that
  manifest.json              - chunk registry + SHA256 hashes
  version.json               - project metadata
  project_meta.json          - author / editor history (always plain JSON)
  wal.log                    - crash protection, cleared on clean close
  checkpoints/
    manual/                  - user-created checkpoints, last 10
    auto/                    - auto on clean close if content changed, last 5
  .lock                      - pid lock
"""

import json
import hashlib
import os
import copy
import threading
import time
import shutil
import zipfile
import psutil
import re
import zlib
import functools
import platformdirs
from pathlib import Path
from typing import Optional, Callable


# ── Constants ─────────────────────────────────────────────────────────────────

LCCA_EXT = ".lcca"
BAK_EXT = ".lcca.bak"
EBAK_EXT = ".lcca.ebak"
BLOB_EXT = ".blob"
MAGIC = b"\x4c\x43\x43\x41"  # LCCA in hex
ENGINE_VER = "3.0.0"
MANUAL_CHECKPOINT_RETENTION = 10
AUTO_CHECKPOINT_RETENTION = 5
MIN_ROTATE_AGE = 0.0  # 0 = always rotate on save (set to 30.0 for production)


# ── Encoding ──────────────────────────────────────────────────────────────────


def _encode(data: dict, readable: bool = False) -> bytes:
    """
    Pure encoding utility.

    readable=True  - plain UTF-8 JSON
    readable=False - MAGIC + zlib compressed JSON (binary)
    """
    if readable:
        return json.dumps(data, indent=4).encode("utf-8")
    compressed = zlib.compress(
        json.dumps(data, separators=(",", ":")).encode("utf-8"),
        level=6,
    )
    return MAGIC + compressed


def _decode(raw: bytes) -> dict:
    """
    Decodes bytes to dict.
    Supports both binary LCCA format and plain JSON (dev mode).
    Raises ValueError if file is not a valid LCCA or JSON file.
    """
    if raw[:4] == MAGIC:
        try:
            return json.loads(zlib.decompress(raw[4:]).decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Corrupt LCCA binary data: {e}")
    # Only attempt plain JSON if the content is valid UTF-8 text.
    # This prevents a defective binary file (with corrupted MAGIC) from being
    # silently misinterpreted as a readable-mode JSON file.
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Not a valid LCCA file: binary data with no LCCA magic.")
    try:
        return json.loads(text)
    except Exception:
        raise ValueError("Not a valid LCCA file.")


# ── Decorator ─────────────────────────────────────────────────────────────────


def requires_active(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self._engine_active:
            self._log(f"Blocked: '{func.__name__}' called on inactive engine.")
            return None
        return func(self, *args, **kwargs)

    return wrapper


# ── Engine ────────────────────────────────────────────────────────────────────


class SafeChunkEngine:
    """
    SafeChunk Engine v3.0

    - Auto-saves every 1-2s via debounce + force-save timers
    - Rolling 3-copy backup per chunk (.lcca / .lcca.bak / .lcca.ebak)
    - WAL for crash protection
    - SHA256 integrity check on open
    - Auto-checkpoint on clean close (last 5 kept)
    - readable=True: plain JSON output; readable=False: binary LCCA (default)
    """

    VERSION = ENGINE_VER
    APP_NAME: str = None
    APP_AUTHOR: str = None
    APP_DATA_NAME: str = None  # separate AppData folder name for user files

    @staticmethod
    def get_default_base_dir(
        use_local: bool = False,
        app_name: str = None,
        app_author: str = None,
        app_data_name: str = None,
    ) -> str:
        """
        Returns the default base directory for projects.
        use_local=True:  Returns "user_projects" (relative to current directory).
        use_local=False: Returns platform-specific AppData path (via platformdirs).
        """
        if use_local:
            path = os.path.abspath(os.path.join("lcca", "user_projects"))
            os.makedirs(path, exist_ok=True)
            return path

        # Resolve defaults
        name = app_name or SafeChunkEngine.APP_NAME
        author = app_author or SafeChunkEngine.APP_AUTHOR
        data_name = app_data_name or SafeChunkEngine.APP_DATA_NAME or name

        if not name or not author:
            # Fallback for safety: if not configured, use local folder instead of crashing
            # But log a warning so developer knows they forgot to configure it.
            print(
                "WARNING: SafeChunkEngine.APP_NAME/AUTHOR not set. "
                "Defaulting to local 'user_projects' folder."
            )
            path = os.path.abspath(os.path.join("lcca", "user_projects"))
            os.makedirs(path, exist_ok=True)
            return path

        # Standard AppData path — uses APP_DATA_NAME so user files live in a
        # separate folder from the app installation folder.
        base = platformdirs.user_data_dir(data_name)
        full_path = os.path.join(base, author, "user_projects")
        os.makedirs(full_path, exist_ok=True)
        return full_path

    def __init__(
        self,
        project_id: str,
        display_name: str = None,
        app_version: str = "1.0.0",
        debounce_delay: float = 1.0,
        force_save_delay: float = 2.0,
        base_dir: str = None,
        readable: bool = False,
        optimize: bool = True,
    ):
        # ── Identity ──────────────────────────────────────────────────────────
        self.project_id = project_id
        self.display_name = display_name or project_id
        self.app_version = app_version
        self.debounce_delay = debounce_delay
        self.force_save_delay = force_save_delay

        # ── Resolve base_dir ──────────────────────────────────────────────────
        if base_dir is None:
            base_dir = self.get_default_base_dir()
        self.base_dir_path = Path(base_dir).resolve()
        
        self.readable = readable

        # ── Optimize mode ─────────────────────────────────────────────────────
        # When True (default):
        #   - WAL fsync is skipped (flush only) - reduces per-write disk stall
        #   - Integrity check is skipped on clean close - faster attach
        #   - WAL removes are batched per commit - fewer file rewrites
        # When False: original safe behaviour, every fsync is honoured.
        self.optimize = optimize

        # ── Paths ─────────────────────────────────────────────────────────────
        self.project_path = self.base_dir_path / self.project_id
        self.chunks_path = self.project_path / "chunks"
        self.chunks_bak_path = self.project_path / "chunks_bak"
        self.checkpoint_path = self.project_path / "checkpoints"
        self.checkpoint_manual = self.checkpoint_path / "manual"
        self.checkpoint_auto = self.checkpoint_path / "auto"
        self.manifest_path = self.project_path / "manifest.json"
        self.blob_manifest_path = self.project_path / "blob_manifest.json"
        self.blobs_path = self.project_path / "blobs"
        self.version_path = self.project_path / "version.json"
        self.project_meta_path = self.project_path / "project_meta.json"
        self.lock_path = self.project_path / ".lock"
        self.wal_path = self.project_path / "wal.log"

        # ── Threading ─────────────────────────────────────────────────────────
        self._write_lock = threading.Lock()
        self._debounce_timer = None
        self._force_save_timer = None

        # ── State ─────────────────────────────────────────────────────────────
        self._staged_data = {}  # chunk_name → dict (uncompressed)
        self._session_dirty = False
        self._engine_active = False
        self.log_history = []

        # ── Callbacks ─────────────────────────────────────────────────────────
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_sync: Optional[Callable[[], None]] = None
        self.on_fault: Optional[Callable[[str], None]] = None
        self.on_dirty: Optional[Callable[[bool], None]] = None

        # ── Boot ──────────────────────────────────────────────────────────────
        self._initialize_env()
        self.attach()

    # --------------------------------------------------------------------------
    # ADMIN FILE I/O  (manifest, version, meta - always plain JSON, never encrypted)
    # --------------------------------------------------------------------------

    def _write_admin(self, path: Path, data: dict) -> None:
        """Write an administrative file as plain JSON. Never encrypted.
        Uses atomic tmp -> fsync -> rename to prevent corruption on crash."""
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, indent=4))
                f.flush()
                os.fsync(f.fileno())
            tmp.replace(path)
        except Exception:
            try:
                tmp.unlink()
            except Exception:
                pass
            raise

    @staticmethod
    def _read_admin(path: Path, default: dict = None) -> dict:
        """Read an administrative file. Returns default ({}) if missing or corrupt.
        Static so static methods (list_all_projects, get_project_info) can call it too.
        Sets _corrupted flag on returned dict if file exists but could not be parsed."""
        if not path.exists():
            return default if default is not None else {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            result = dict(default) if default is not None else {}
            result["_corrupted"] = True
            return result

    # --------------------------------------------------------------------------
    # ENVIRONMENT
    # --------------------------------------------------------------------------

    def _initialize_env(self):
        """Creates folder structure."""
        for path in [
            self.chunks_path,
            self.chunks_bak_path,
            self.checkpoint_manual,
            self.checkpoint_auto,
            self.blobs_path,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def _startup_gc(self):
        """
        Runs on attach. Removes:
          - Stale *.tmp files left by a crashed atomic write
          - Orphaned .bak/.ebak files whose .lcca no longer exists
        """
        # Stale tmp files in chunks dir
        for tmp in self.chunks_path.glob("*.tmp"):
            try:
                tmp.unlink()
                self._log(f"GC: Removed stale tmp: {tmp.name}")
            except Exception:
                pass

        # Stale tmp files from crashed admin writes (version.json.tmp, manifest.json.tmp)
        for tmp in self.project_path.glob("*.tmp"):
            try:
                tmp.unlink()
                self._log(f"GC: Removed stale admin tmp: {tmp.name}")
            except Exception:
                pass

        # Orphaned backups
        current = {
            f.name[: -len(LCCA_EXT)] for f in self.chunks_path.glob(f"*{LCCA_EXT}")
        }
        for ext in (BAK_EXT, EBAK_EXT):
            for f in self.chunks_bak_path.glob(f"*{ext}"):
                stem = f.name[: -len(ext)]
                if stem not in current:
                    try:
                        f.unlink()
                        self._log(f"GC: Removed orphan: {f.name}")
                    except Exception:
                        pass

        # Stale blob tmp files
        for tmp in self.blobs_path.glob("*.tmp"):
            try:
                tmp.unlink()
                self._log(f"GC: Removed stale blob tmp: {tmp.name}")
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # LIFECYCLE
    # --------------------------------------------------------------------------

    def _write_lock_file(self):
        try:
            proc = psutil.Process(os.getpid())
            create_time = proc.create_time()
        except Exception:
            create_time = 0.0
        self.lock_path.write_text(f"PID: {os.getpid()}\nCREATED: {create_time}")

    @staticmethod
    def _is_lock_live(lock_path: Path) -> bool:
        """
        Returns True only if the lock belongs to a process that is STILL running
        AND has the same creation time as when the lock was written.
        Pure PID existence is not enough - PIDs are recycled after power failures.
        """
        try:
            text = lock_path.read_text()
            pid = int(text.split("PID:")[1].split()[0].strip())

            if not psutil.pid_exists(pid):
                return False

            # Check creation time to guard against PID recycling
            stored_created = float(text.split("CREATED:")[1].strip())
            actual_created = psutil.Process(pid).create_time()

            # Allow 2s tolerance for clock jitter
            return abs(actual_created - stored_created) < 2.0

        except Exception:
            # If we can't parse/verify, treat as stale - safer than blocking forever
            return False

    def attach(self):
        if self.lock_path.exists():
            if self._is_lock_live(self.lock_path):
                self._engine_active = False
                self._log("ATTACH_DENIED: Project is open in another window.")
                return
            else:
                self._log("Removing stale lock (process gone or PID recycled).")
                try:
                    self.lock_path.unlink()
                except Exception as e:
                    self._log(f"Could not remove stale lock: {e}")

        try:
            # ── Read existing version.json ────────────────────────────────────
            existing_version = self._read_admin(self.version_path)

            # ── Detect corrupt version.json ───────────────────────────────────
            if existing_version.pop("_corrupted", False):
                self._log(
                    "WARNING: version.json is corrupt and could not be parsed. "
                    "Treating session as unclean - integrity check will run."
                )
                existing_version["clean_close"] = False

            # ── Lock readable mode to what's stored on disk ───────────────────
            # If project already exists, readable is NEVER allowed to change.
            # A binary project must always stay binary.
            if existing_version and "readable" in existing_version:
                stored_readable = existing_version["readable"]
                if self.readable != stored_readable:
                    self._log(
                        f"WARNING: readable={self.readable} was requested but project "
                        f"is stored as readable={stored_readable}. Enforcing stored setting."
                    )
                    self.readable = stored_readable

            # ── Preserve display_name ─────────────────────────────────────────
            saved_name = existing_version.get("display_name", "").strip()
            if self.display_name and self.display_name != self.project_id:
                final_name = self.display_name
            elif saved_name and saved_name != self.project_id:
                final_name = saved_name
            else:
                final_name = self.project_id
            self.display_name = final_name

            # ── Claim lock ────────────────────────────────────────────────────
            self._write_lock_file()

            # ── Cache close_count for first-run detection ─────────────────────
            self.close_count = existing_version.get("close_count", 0)

            # ── Mark session unclean immediately ──────────────────────────────
            # If we crash before detach(), clean_close stays False on disk
            self._write_version(existing_version, clean_close=False)

            # ── Startup GC ────────────────────────────────────────────────────
            self._startup_gc()

            # ── WAL replay ────────────────────────────────────────────────────
            replayed = self._wal_replay()
            if replayed:
                self._session_dirty = True

            # ── Integrity check ───────────────────────────────────────────────
            # optimize=True : skipped if last close was clean (no crash).
            #                 The WAL would have replayed any uncommitted writes,
            #                 so a full hash pass is redundant after a clean close.
            # optimize=False: always runs, original behaviour.
            last_clean = existing_version.get("clean_close", True)
            if not last_clean:
                self._log(
                    "Last session was unclean - running integrity check after WAL replay."
                )
            skip_check = self.optimize and last_clean and not replayed
            if skip_check:
                self._log(
                    "Optimize: clean close detected - skipping full integrity check."
                )
                damaged = []
            else:
                damaged = self._verify_chunks()
            if damaged:
                self._log(
                    f"Integrity: {len(damaged)} chunk(s) failed hash check "
                    f"{damaged} - restoring from backup."
                )
                unrecovered = []
                for name in damaged:
                    if not self._restore_chunk_from_backup(name):
                        unrecovered.append(name)
                if unrecovered:
                    # Write an empty chunk file for each unrecoverable chunk so
                    # that future reads return {} silently instead of re-firing
                    # the "missing" error on every subsequent open.  The manifest
                    # entry is also removed so the integrity check won't flag it.
                    _m = self._load_manifest()
                    _c = _m.get("chunks", {})
                    for name in unrecovered:
                        try:
                            lcca_path = self.chunks_path / f"{name}{LCCA_EXT}"
                            lcca_path.write_bytes(_encode({}, self.readable))
                            self._log(
                                f"Wrote empty placeholder for lost chunk '{name}'."
                            )
                        except Exception as _e:
                            self._log(f"Could not write placeholder for '{name}': {_e}")
                        _c.pop(name, None)
                    _m["chunks"] = _c
                    self._save_manifest(_m)
                    self._handle_error(
                        f"Could not restore {len(unrecovered)} chunk(s) - "
                        f"no valid backup found: {unrecovered}. "
                        f"Data for these chunks is permanently lost."
                    )

            # ── Blob integrity check ───────────────────────────────────────────
            # optimize=True : skipped if last close was clean, same rationale
            #                 as the chunk integrity check above.
            # optimize=False: always runs.
            if skip_check:
                self._log(
                    "Optimize: clean close detected - skipping blob integrity check."
                )
                damaged_blobs = []
            else:
                damaged_blobs = self._verify_blobs()
            if damaged_blobs:
                # Remove damaged blobs from manifest immediately so the same
                # error does not re-fire on every subsequent open.
                _bm = self._load_blob_manifest()
                _bl = _bm.get("blobs", {})
                for name in damaged_blobs:
                    _bl.pop(name, None)
                _bm["blobs"] = _bl
                self._write_admin(self.blob_manifest_path, _bm)
                # Mark dirty so _update_blob_manifest_hashes runs on detach.
                self._session_dirty = True
                self._handle_error(
                    f"{len(damaged_blobs)} blob(s) are missing or corrupt: "
                    f"{damaged_blobs}. These files need to be re-uploaded."
                )

            self._engine_active = True
            self._log(
                f"Engine v{self.VERSION} attached to "
                f"'{self.display_name}' ({self.project_id})."
                + (f" WAL replayed {replayed} entries." if replayed else "")
                + (" [readable mode]" if self.readable else "")
                + (" [optimize=True]" if self.optimize else " [optimize=False]")
            )

        except Exception as e:
            self._engine_active = False
            self._handle_error(f"Critical attach failure: {e}")

    def detach(self):
        """
        Safe close sequence:
          1. Force sync all staged data
          2. Cancel timers
          3. Update manifest hashes
          4. Auto-checkpoint if session was dirty
          5. Clear WAL
          6. Write clean version.json
          7. Remove stale tmps (final cleanup)
          8. Release lock
        """
        if not self._engine_active:
            return

        self._log("Detaching. Final sync...")
        self.force_sync()

        # ── Cancel timers ─────────────────────────────────────────────────────
        with self._write_lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
                self._debounce_timer = None
            if self._force_save_timer:
                self._force_save_timer.cancel()
                self._force_save_timer = None

        # ── Update manifest hashes (only if data changed) ────────────────────
        if self._session_dirty:
            self._update_manifest_hashes()
            self._update_blob_manifest_hashes()

        # ── Auto-checkpoint if content changed since last checkpoint ──────────
        if self._session_dirty and self._checkpoint_needed():
            try:
                self._create_auto_checkpoint()
                self._log("Auto-close checkpoint created.")
            except Exception as e:
                self._log(f"Auto-close checkpoint failed: {e}")

        # ── Clear WAL ─────────────────────────────────────────────────────────
        self._wal_clear()

        # ── Final GC: remove any stale tmps ──────────────────────────────────
        for tmp in self.chunks_path.glob("*.tmp"):
            try:
                tmp.unlink()
            except Exception:
                pass

        # ── Write clean version.json ──────────────────────────────────────────
        self._write_version(self._read_admin(self.version_path), clean_close=True)

        # ── Release lock ──────────────────────────────────────────────────────
        if self.lock_path.exists():
            self.lock_path.unlink()

        self._engine_active = False
        self._log("Engine detached cleanly.")

    def is_active(self) -> bool:
        return self._engine_active

    def is_dirty(self) -> bool:
        with self._write_lock:
            return bool(self._staged_data)

    # --------------------------------------------------------------------------
    # VERSION.JSON
    # --------------------------------------------------------------------------

    def _write_version(self, base: dict, clean_close: bool):
        """Writes version.json merging base dict with current engine state."""
        data = {
            **base,
            "engine_version": self.VERSION,
            "app_version": self.app_version,
            "project_id": self.project_id,
            "display_name": self.display_name,
            "readable": self.readable,
            "clean_close": clean_close,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if clean_close:
            data["close_count"] = base.get("close_count", 0) + 1
        try:
            self._write_admin(self.version_path, data)
        except Exception as e:
            self._log(f"version.json write failed: {e}")

    # --------------------------------------------------------------------------
    # MANIFEST
    # --------------------------------------------------------------------------

    def _load_manifest(self) -> dict:
        if not self.manifest_path.exists():
            self._log(
                "WARNING: manifest.json is missing. "
                "Integrity check will be skipped this session. "
                "Hashes will be rebuilt on next clean close."
            )
            return {"chunks": {}}
        manifest = self._read_admin(self.manifest_path, default={"chunks": {}})
        if manifest.pop("_corrupted", False):
            self._log(
                "WARNING: manifest.json is corrupt and could not be parsed. "
                "Integrity check will recompute hashes from disk."
            )
            return {"chunks": {}}
        return manifest

    def _save_manifest(self, manifest: dict):
        tmp = self.manifest_path.with_suffix(".tmp")
        try:
            self._write_admin(tmp, manifest)
            tmp.replace(self.manifest_path)
        except Exception as e:
            self._log(f"Manifest save failed: {e}")

    def _update_manifest_hashes(self):
        """
        Computes SHA256 of every .lcca file and writes to manifest.json.
        Called on detach() - enables integrity check on next open.
        """
        manifest = self._load_manifest()
        chunks = manifest.get("chunks", {})

        # Prune entries for files that no longer exist so they don't
        # trigger repeated "missing" errors on future opens.
        existing = {
            lcca.name[: -len(LCCA_EXT)]
            for lcca in self.chunks_path.glob(f"*{LCCA_EXT}")
        }
        for stale in [k for k in list(chunks) if k not in existing]:
            del chunks[stale]
            self._log(f"Manifest: removed stale entry for missing chunk '{stale}'.")

        for lcca in self.chunks_path.glob(f"*{LCCA_EXT}"):
            chunk_name = lcca.name[: -len(LCCA_EXT)]
            try:
                file_hash = hashlib.sha256(lcca.read_bytes()).hexdigest()
                chunks[chunk_name] = {
                    "hash": file_hash,
                    "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            except Exception as e:
                self._log(f"Hash failed for {chunk_name}: {e}")

        manifest["chunks"] = chunks
        manifest["project_id"] = self.project_id
        manifest["engine_version"] = self.VERSION
        manifest["hashes_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save_manifest(manifest)
        self._log("Manifest hashes updated.")

    def _verify_chunks(self) -> list[str]:
        """
        Verifies each .lcca file against stored SHA256 in manifest.
        Returns list of chunk names that failed - empty list means all good.
        """
        manifest = self._load_manifest()
        chunks = manifest.get("chunks", {})
        damaged = []

        for chunk_name, info in chunks.items():
            if not isinstance(info, dict):
                continue
            stored_hash = info.get("hash")
            if not stored_hash:
                continue
            lcca = self.chunks_path / f"{chunk_name}{LCCA_EXT}"
            if not lcca.exists():
                damaged.append(chunk_name)
                continue
            try:
                if hashlib.sha256(lcca.read_bytes()).hexdigest() != stored_hash:
                    damaged.append(chunk_name)
            except Exception:
                damaged.append(chunk_name)

        return damaged

    def _restore_chunk_from_backup(self, chunk_name: str) -> bool:
        """
        Attempts to restore a damaged .lcca from .bak then .ebak.
        Returns True if a valid backup was found and restored.
        """
        lcca = self.chunks_path / f"{chunk_name}{LCCA_EXT}"
        bak = self.chunks_bak_path / f"{chunk_name}{BAK_EXT}"
        ebak = self.chunks_bak_path / f"{chunk_name}{EBAK_EXT}"

        for src, label in [(bak, ".bak"), (ebak, ".ebak")]:
            if not src.exists():
                continue
            try:
                _decode(src.read_bytes())  # verify before restoring
                shutil.copy2(src, lcca)
                self._log(f"Restored {chunk_name} from {label}.")
                return True
            except Exception as e:
                self._log(f"{label} invalid/corrupt for {chunk_name}: {e}")

        self._handle_error(
            f"No valid backup found for '{chunk_name}' - "
            f".bak and .ebak are both missing or corrupt. "
            f"This chunk's data is permanently lost."
        )
        return False

    # --------------------------------------------------------------------------
    # WAL (WRITE-AHEAD LOG)
    # --------------------------------------------------------------------------

    def _wal_append(self, chunk_name: str, data: dict):
        """Synchronously appends a WAL entry before any disk write.

        optimize=True  - flush only (no fsync). Faster; tiny crash window
                         between flush and the OS writing through to disk.
        optimize=False - full fsync, original safe behaviour.
        """
        try:
            entry = json.dumps(
                {"chunk": chunk_name, "ts": time.time(), "data": data},
                separators=(",", ":"),
            )
            crc = zlib.crc32(entry.encode()) & 0xFFFFFFFF
            record = json.dumps({"e": entry, "crc": crc}, separators=(",", ":")) + "\n"
            with open(self.wal_path, "a", encoding="utf-8") as f:
                f.write(record)
                f.flush()
                if not self.optimize:
                    os.fsync(f.fileno())
        except Exception as e:
            self._log(f"WAL append failed: {e}")

    def _wal_remove(self, chunk_name: str):
        """Removes committed entries for a single chunk. Thin wrapper over _wal_remove_batch."""
        self._wal_remove_batch([chunk_name])

    def _wal_remove_batch(self, chunk_names: list):
        """Removes committed entries for multiple chunks in a single WAL rewrite.

        optimize=True  - called once after all chunks in a commit are written,
                         avoiding O(n) rewrites per chunk.
        optimize=False - behaviour is identical; batching is always safe.
        """
        if not self.wal_path.exists():
            return
        names = set(chunk_names)
        try:
            lines = self.wal_path.read_text(encoding="utf-8").splitlines()
            remaining = []
            for line in lines:
                try:
                    rec = json.loads(line)
                    entry = json.loads(rec["e"])
                    if entry.get("chunk") not in names:
                        remaining.append(line)
                except Exception:
                    remaining.append(line)
            if remaining:
                self.wal_path.write_text("\n".join(remaining) + "\n", encoding="utf-8")
            else:
                self.wal_path.unlink()
        except Exception as e:
            self._log(f"WAL remove failed: {e}")

    def _wal_replay(self) -> int:
        """
        Replays uncommitted WAL entries into _staged_data.
        Called on attach if WAL exists.
        Returns number of entries successfully replayed.
        """
        if not self.wal_path.exists():
            return 0

        replayed = 0
        try:
            for line in self.wal_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    raw = rec["e"]
                    actual_crc = zlib.crc32(raw.encode()) & 0xFFFFFFFF
                    if actual_crc != rec["crc"]:
                        self._log("WAL: CRC mismatch - skipping corrupt entry.")
                        continue
                    entry = json.loads(raw)
                    chunk_name = entry.get("chunk", "").strip()
                    data = entry.get("data")
                    if chunk_name and data is not None:
                        self._staged_data[chunk_name] = data
                        replayed += 1
                except Exception as e:
                    self._log(f"WAL: Skipping unreadable entry: {e}")
        except Exception as e:
            self._log(f"WAL replay failed: {e}")

        return replayed

    def _wal_clear(self):
        """Removes WAL file on clean close."""
        try:
            if self.wal_path.exists():
                self.wal_path.unlink()
                self._log("WAL cleared.")
        except Exception as e:
            self._log(f"WAL clear failed: {e}")

    # --------------------------------------------------------------------------
    # CORE DATA OPERATIONS
    # --------------------------------------------------------------------------

    @requires_active
    def stage_update(self, data: dict, chunk_name: str):
        """
        Buffers data in memory and triggers debounce + force-save timers.
        Appends to WAL immediately for crash protection.
        """
        if not self._safe_name(chunk_name):
            self._log(
                f"WARNING: stage_update rejected unsafe chunk_name: {chunk_name!r}"
            )
            return

        with self._write_lock:
            self._staged_data[chunk_name] = copy.deepcopy(data)
            self._wal_append(chunk_name, data)

            # Debounce - resets on every call
            if self._debounce_timer:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(
                self.debounce_delay, self._commit_to_disk
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

            # Force-save - fires once per burst, guaranteed
            if self._force_save_timer is None:
                self._force_save_timer = threading.Timer(
                    self.force_save_delay, self._force_save_from_timer
                )
                self._force_save_timer.daemon = True
                self._force_save_timer.start()

        if self.on_dirty:
            self.on_dirty(True)
        if self.on_status:
            self.on_status("Unsaved changes...")

    @requires_active
    def fetch_chunk(self, chunk_name: str) -> dict:
        """
        Returns chunk data.
        Priority: staged memory → .lcca → .lcca.bak → .lcca.ebak → {}
        """
        if not self._safe_name(chunk_name):
            self._log(
                f"WARNING: fetch_chunk rejected unsafe chunk_name: {chunk_name!r}"
            )
            return {}
        with self._write_lock:
            if chunk_name in self._staged_data:
                return copy.deepcopy(self._staged_data[chunk_name])
        return self._read_chunk_with_fallback(chunk_name)

    # Alias for backward compatibility
    read_chunk = fetch_chunk

    def _read_chunk_with_fallback(self, chunk_name: str) -> dict:
        """Reads .lcca with automatic fallback to .bak then .ebak."""
        lcca = self.chunks_path / f"{chunk_name}{LCCA_EXT}"
        bak = self.chunks_bak_path / f"{chunk_name}{BAK_EXT}"
        ebak = self.chunks_bak_path / f"{chunk_name}{EBAK_EXT}"

        for src, label in [(lcca, ".lcca"), (bak, ".bak"), (ebak, ".ebak")]:
            if not src.exists():
                continue
            try:
                data = _decode(src.read_bytes())
                if label != ".lcca":
                    self._handle_error(
                        f"'{chunk_name}.lcca' is missing or unreadable at runtime - "
                        f"serving data from {label}. "
                        f"Data may be one save behind."
                    )
                return data
            except Exception as e:
                self._log(f"Read failed {chunk_name}{label}: {e}. Trying next.")

        # All copies are gone. Write an empty placeholder so this message
        # never fires again for the same chunk on future opens.
        try:
            lcca.write_bytes(_encode({}, self.readable))
            self._log(
                f"All copies of '{chunk_name}' were missing - "
                f"wrote empty placeholder. Data for this chunk is lost."
            )
        except Exception as _e:
            self._log(f"Could not write placeholder for '{chunk_name}': {_e}")
        return {}

    @requires_active
    def force_sync(self):
        """Immediately flushes all staged data to disk."""
        with self._write_lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
                self._debounce_timer = None
            if self._force_save_timer:
                self._force_save_timer.cancel()
                self._force_save_timer = None
        self._commit_to_disk()

    def _force_save_from_timer(self):
        with self._write_lock:
            self._force_save_timer = None
        self._commit_to_disk()
        self._log(f"Force-save fired after {self.force_save_delay}s.")

    # --------------------------------------------------------------------------
    # ATOMIC WRITE + ROTATION
    # --------------------------------------------------------------------------

    def _commit_to_disk(self):
        """Writes all staged chunks to disk atomically with rotation.

        optimize=True  - collects all successfully written chunk names and
                         removes them from the WAL in a single rewrite pass.
        optimize=False - removes each chunk from WAL individually after write
                         (original behaviour, one rewrite per chunk).
        """
        with self._write_lock:
            if not self._staged_data or not self._engine_active:
                return

            failed = []
            committed = []
            for chunk_name, data in list(self._staged_data.items()):
                try:
                    self._write_chunk(chunk_name, data)
                    del self._staged_data[chunk_name]
                    if self.optimize:
                        committed.append(chunk_name)  # batch for single WAL rewrite
                    else:
                        self._wal_remove(chunk_name)  # original: one rewrite per chunk
                except Exception as e:
                    failed.append(chunk_name)
                    self._log(f"Commit failed for {chunk_name}: {e}")

            # Batched WAL remove - single file rewrite for all committed chunks
            if self.optimize and committed:
                self._wal_remove_batch(committed)

            self._debounce_timer = None
            self._session_dirty = True

            if failed:
                self._handle_error(f"Commit failed for: {failed}")
            else:
                if self.on_dirty:
                    self.on_dirty(False)
                if self.on_sync:
                    self.on_sync()
                self._log("Commit successful.")

    def _write_chunk(self, chunk_name: str, data: dict):
        """
        Atomic write with rolling rotation:
          lcca  → ebak   (previous current pushed back)
          new   → tmp → lcca  (atomic fsync + rename)
          lcca  → bak    (mirror of current, always identical to lcca)

        Result after each save:
          lcca  = current
          bak   = mirror of current
          ebak  = previous current (one save behind)
        """
        lcca = self.chunks_path / f"{chunk_name}{LCCA_EXT}"
        bak = self.chunks_bak_path / f"{chunk_name}{BAK_EXT}"
        ebak = self.chunks_bak_path / f"{chunk_name}{EBAK_EXT}"

        encoded = _encode(data, self.readable)

        # Skip if content unchanged
        if lcca.exists():
            try:
                if lcca.read_bytes() == encoded:
                    return
            except Exception:
                pass

        # Current lcca → ebak before overwriting (only if valid - never rotate a corrupt file)
        if lcca.exists():
            try:
                _decode(lcca.read_bytes())
                shutil.copy2(lcca, ebak)
            except Exception:
                self._log(
                    f"WARNING: existing {chunk_name}.lcca is corrupt - skipping rotation to ebak."
                )

        # Atomic write: tmp → fsync → rename
        tmp = lcca.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(lcca)

        # Mirror current lcca → bak (safety copy, always same as lcca)
        shutil.copy2(lcca, bak)

    # --------------------------------------------------------------------------
    # CHECKPOINTS
    # --------------------------------------------------------------------------

    def _checkpoint_needed(self) -> bool:
        """
        Returns True if current chunk state differs from last auto checkpoint.
        Compares manifest hashes - cheap and accurate.
        Always returns True if no checkpoint exists yet.
        """
        last_cps = sorted(
            self.checkpoint_auto.glob("cp_*.3ps"),
            key=os.path.getmtime,
            reverse=True,
        )
        if not last_cps:
            return True

        try:
            with zipfile.ZipFile(last_cps[0], "r") as zf:
                if "manifest.json" not in zf.namelist():
                    return True
                old_manifest = json.loads(zf.read("manifest.json").decode("utf-8"))

            current_manifest = self._load_manifest()

            old_hashes = {
                k: v.get("hash") if isinstance(v, dict) else v
                for k, v in old_manifest.get("chunks", {}).items()
            }
            current_hashes = {
                k: v.get("hash") if isinstance(v, dict) else v
                for k, v in current_manifest.get("chunks", {}).items()
            }
            return old_hashes != current_hashes

        except Exception:
            return True  # if anything fails, create checkpoint to be safe

    def _create_auto_checkpoint(self) -> str | None:
        """Creates an auto checkpoint in checkpoints/auto/.
        Never includes blobs - must stay fast for clean close."""
        return self._write_checkpoint(
            folder=self.checkpoint_auto,
            label="auto_close",
            notes="Automatic checkpoint on clean close.",
            retention=AUTO_CHECKPOINT_RETENTION,
            include_blobs=False,
        )

    @requires_active
    def create_checkpoint(
        self, label: str = "manual", notes: str = "", include_blobs: bool = False
    ) -> str | None:
        """
        Creates a manual checkpoint in checkpoints/manual/.
        Keeps last MANUAL_CHECKPOINT_RETENTION checkpoints.

        include_blobs=False (default): chunks only - fast, small ZIP.
        include_blobs=True: chunks + blobs - full snapshot, can be large.
          Use for a true point-in-time backup before major changes.
          Blob hashes are always recorded in checkpoint_meta.json regardless,
          so mismatches can be detected even when blobs are not included.
        """
        return self._write_checkpoint(
            folder=self.checkpoint_manual,
            label=label,
            notes=notes,
            retention=MANUAL_CHECKPOINT_RETENTION,
            include_blobs=include_blobs,
        )

    def _write_checkpoint(
        self,
        folder: Path,
        label: str,
        notes: str,
        retention: int,
        include_blobs: bool = False,
    ) -> str | None:
        """
        Core checkpoint writer.
        Writes ZIP + SHA256 to specified folder, enforces retention.

        include_blobs=False: chunks only - fast, no blob data in ZIP.
        include_blobs=True: chunks + blobs - full snapshot.

        Blob hashes are always written into checkpoint_meta.json regardless
        of include_blobs, so restore can detect blob mismatches even when
        blobs were not included in the ZIP.
        """
        self.force_sync()

        clean_label = re.sub(r"[^\w\-_]", "_", label)[:30]
        timestamp = (
            time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
        )
        zip_name = f"cp_{clean_label}_{timestamp}.3ps"
        zip_path = folder / zip_name

        # Snapshot blob hashes at checkpoint time (always, regardless of include_blobs)
        blob_manifest = self._load_blob_manifest()
        blob_hashes = {
            name: info.get("hash") if isinstance(info, dict) else info
            for name, info in blob_manifest.get("blobs", {}).items()
        }

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in self.chunks_path.glob(f"*{LCCA_EXT}"):
                    zf.write(f, arcname=f"chunks/{f.name}")
                if self.manifest_path.exists():
                    zf.write(self.manifest_path, arcname="manifest.json")
                if self.version_path.exists():
                    zf.write(self.version_path, arcname="version.json")

                # Include blobs only when explicitly requested
                if include_blobs:
                    for f in self.blobs_path.glob(f"*{BLOB_EXT}"):
                        zf.write(f, arcname=f"blobs/{f.name}")
                    if self.blob_manifest_path.exists():
                        zf.write(self.blob_manifest_path, arcname="blob_manifest.json")

                zf.writestr(
                    "checkpoint_meta.json",
                    json.dumps(
                        {
                            "label": label,
                            "notes": notes,
                            "timestamp": timestamp,
                            "project_id": self.project_id,
                            "display_name": self.display_name,
                            "engine_ver": self.VERSION,
                            "app_ver": self.app_version,
                            "readable": self.readable,
                            "type": (
                                "auto" if folder == self.checkpoint_auto else "manual"
                            ),
                            "includes_blobs": include_blobs,
                            "blob_hashes": blob_hashes,  # always recorded
                        },
                        indent=4,
                    ),
                )

            # Write SHA256 alongside ZIP
            sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
            (folder / f"{zip_name}.sha256").write_text(sha)

            # Enforce retention for this folder only
            zips = sorted(folder.glob("cp_*.3ps"), key=os.path.getmtime)
            while len(zips) > retention:
                oldest = zips.pop(0)
                oldest.unlink()
                sha_file = folder / f"{oldest.name}.sha256"
                if sha_file.exists():
                    sha_file.unlink()

            self._log(f"Checkpoint created: {folder.name}/{zip_name}")
            return zip_name

        except Exception as e:
            self._handle_error(f"Checkpoint failed: {e}")
            return None

    def _resolve_checkpoint_path(self, zip_name: str) -> Path | None:
        """Finds which folder (manual/auto) a checkpoint lives in."""
        for folder in (self.checkpoint_manual, self.checkpoint_auto):
            p = folder / zip_name
            if p.exists():
                return p
        return None

    def verify_checkpoint(self, zip_name: str) -> bool:
        """
        Verifies checkpoint SHA256.
        Returns True if verified or no .sha256 exists (legacy).
        Returns False if hash mismatch or file missing.
        """
        zip_path = self._resolve_checkpoint_path(zip_name)
        if zip_path is None:
            return False

        sha_path = zip_path.parent / f"{zip_name}.sha256"
        if not sha_path.exists():
            return True  # legacy - no hash file, trust it

        try:
            stored = sha_path.read_text().strip()
            actual = hashlib.sha256(zip_path.read_bytes()).hexdigest()
            return stored == actual
        except Exception:
            return False

    @requires_active
    def restore_checkpoint(self, zip_name: str) -> bool:
        """
        Restores project from checkpoint ZIP.
        Verifies SHA256 before extracting.

        If the checkpoint includes blobs (include_blobs=True was used),
        blobs on disk are fully replaced with the checkpoint's copies.

        If the checkpoint does not include blobs, chunk data is restored
        but blobs on disk are left untouched. A warning is logged listing
        any blobs whose current hash differs from what was recorded at
        checkpoint time, so the caller knows which files may be mismatched.
        """
        zip_path = self._resolve_checkpoint_path(zip_name)
        if zip_path is None:
            self._log(f"Checkpoint not found: {zip_name}")
            return False

        if not self.verify_checkpoint(zip_name):
            self._log(f"Restore aborted: {zip_name} failed SHA256 verification.")
            return False

        staging = self.project_path / "_restore_staging"
        try:
            with self._write_lock:
                if self._debounce_timer:
                    self._debounce_timer.cancel()
                    self._debounce_timer = None
                if self._force_save_timer:
                    self._force_save_timer.cancel()
                    self._force_save_timer = None
                self._staged_data.clear()

            if staging.exists():
                shutil.rmtree(staging)
            staging.mkdir()

            with zipfile.ZipFile(zip_path, "r") as zf:
                # ── ZIP bomb check ────────────────────────────────────────
                MAX_EXTRACT_BYTES = 512 * 1024 * 1024  # 512 MB
                total = sum(m.file_size for m in zf.infolist())
                if total > MAX_EXTRACT_BYTES:
                    raise ValueError(
                        f"Archive is too large to extract "
                        f"({total / 1024 / 1024:.0f} MB, limit 512 MB)."
                    )
                # ── ZIP Slip check - safe member-by-member extraction ─────
                staging_resolved = staging.resolve()
                for member in zf.infolist():
                    target = (staging / member.filename).resolve()
                    if not str(target).startswith(str(staging_resolved)):
                        raise ValueError(f"Unsafe path in archive: '{member.filename}'")
                    zf.extract(member, staging)

            if (staging / "chunks").exists():
                if self.chunks_path.exists():
                    shutil.rmtree(self.chunks_path)
                shutil.move(str(staging / "chunks"), str(self.chunks_path))

            # Clear stale bak files - they'll rebuild naturally on next save
            if self.chunks_bak_path.exists():
                shutil.rmtree(self.chunks_bak_path)
            self.chunks_bak_path.mkdir(parents=True, exist_ok=True)

            if (staging / "manifest.json").exists():
                shutil.move(str(staging / "manifest.json"), str(self.manifest_path))

            # ── Blob restore ──────────────────────────────────────────────────
            meta = {}
            meta_path = staging / "checkpoint_meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            if (staging / "blobs").exists():
                # Full blob restore - checkpoint was created with include_blobs=True
                if self.blobs_path.exists():
                    shutil.rmtree(self.blobs_path)
                shutil.move(str(staging / "blobs"), str(self.blobs_path))
                if (staging / "blob_manifest.json").exists():
                    shutil.move(
                        str(staging / "blob_manifest.json"),
                        str(self.blob_manifest_path),
                    )
                self._log("Blobs restored from checkpoint.")
            else:
                # Blobs not in checkpoint - check for mismatches and warn
                cp_blob_hashes = meta.get("blob_hashes", {})
                if cp_blob_hashes:
                    current_blob_manifest = self._load_blob_manifest()
                    current_hashes = {
                        name: info.get("hash") if isinstance(info, dict) else info
                        for name, info in current_blob_manifest.get("blobs", {}).items()
                    }
                    mismatched = [
                        name
                        for name, cp_hash in cp_blob_hashes.items()
                        if current_hashes.get(name) != cp_hash
                    ]
                    missing = [
                        name
                        for name in cp_blob_hashes
                        if not (self.blobs_path / f"{name}{BLOB_EXT}").exists()
                    ]
                    if missing:
                        self._handle_error(
                            f"Checkpoint restored (chunks only). "
                            f"{len(missing)} blob(s) expected by this checkpoint "
                            f"are missing from disk: {missing}. Re-upload them."
                        )
                    elif mismatched:
                        self._log(
                            f"Checkpoint restored (chunks only). "
                            f"{len(mismatched)} blob(s) on disk differ from "
                            f"checkpoint state: {mismatched}. "
                            f"Use create_checkpoint(include_blobs=True) for a full snapshot."
                        )

            shutil.rmtree(staging, ignore_errors=True)
            self._wal_clear()
            self._log(f"Restored from checkpoint: {zip_name}")
            return True

        except Exception as e:
            shutil.rmtree(staging, ignore_errors=True)
            self._handle_error(f"Restore failed: {e}")
            return False

    def list_checkpoints(self) -> list[dict]:
        """
        Lists all checkpoints (manual + auto) with metadata and verification.
        Unverified checkpoints include a warning message.
        """
        results = []
        sources = [
            (self.checkpoint_manual, "manual"),
            (self.checkpoint_auto, "auto"),
        ]

        for folder, cp_type in sources:
            for zp in folder.glob("cp_*.3ps"):
                try:
                    verified = self.verify_checkpoint(zp.name)
                    meta = {}
                    try:
                        with zipfile.ZipFile(zp, "r") as zf:
                            meta = json.loads(
                                zf.read("checkpoint_meta.json").decode("utf-8")
                            )
                    except Exception:
                        pass

                    results.append(
                        {
                            "filename": zp.name,
                            "type": cp_type,
                            "label": meta.get("label", ""),
                            "date": meta.get("timestamp", ""),
                            "notes": meta.get("notes", ""),
                            "verified": verified,
                            "includes_blobs": meta.get("includes_blobs", False),
                            "blob_count": len(meta.get("blob_hashes", {})),
                            "warning": (
                                ""
                                if verified
                                else "Integrity of this checkpoint could not be verified."
                            ),
                            "size_kb": round(zp.stat().st_size / 1024, 1),
                        }
                    )
                except Exception:
                    continue

        return sorted(results, key=lambda x: x["date"], reverse=True)

    def delete_checkpoint(self, zip_name: str) -> bool:
        """Deletes a checkpoint ZIP and its .sha256 sidecar."""
        zip_path = self._resolve_checkpoint_path(zip_name)
        if zip_path is None:
            self._log(f"delete_checkpoint: '{zip_name}' not found.")
            return False
        try:
            zip_path.unlink()
            sha_path = zip_path.parent / f"{zip_name}.sha256"
            if sha_path.exists():
                sha_path.unlink()
            self._log(f"Checkpoint deleted: {zip_name}")
            return True
        except Exception as e:
            self._handle_error(f"delete_checkpoint failed: {e}")
            return False

    # --------------------------------------------------------------------------
    # ROLLBACK HELPERS
    # --------------------------------------------------------------------------

    def list_chunks(self) -> list[str]:
        """Returns names of all stored chunks."""
        return [f.name[: -len(LCCA_EXT)] for f in self.chunks_path.glob(f"*{LCCA_EXT}")]

    @requires_active
    def delete_chunk(self, chunk_name: str) -> bool:
        """
        Permanently deletes a chunk and all its backup copies from disk.
        Clears any staged (unsaved) version from memory, removes WAL entries
        to prevent crash-replay resurrection, and prunes the manifest entry.
        Returns True on success, False if the chunk did not exist or deletion failed.
        """
        if not self._safe_name(chunk_name):
            self._log(f"delete_chunk: rejected unsafe chunk_name: {chunk_name!r}")
            return False

        lcca = self.chunks_path     / f"{chunk_name}{LCCA_EXT}"
        bak  = self.chunks_bak_path / f"{chunk_name}{BAK_EXT}"
        ebak = self.chunks_bak_path / f"{chunk_name}{EBAK_EXT}"

        try:
            # Hold the write lock while clearing staged data and unlinking .lcca
            # so a concurrent _commit_to_disk can't write the chunk back between steps.
            # Do NOT cancel _debounce_timer here - it is shared across all chunks.
            with self._write_lock:
                was_staged = chunk_name in self._staged_data
                self._staged_data.pop(chunk_name, None)

                if not lcca.exists() and not was_staged:
                    self._log(f"delete_chunk: '{chunk_name}' not found.")
                    return False

                if lcca.exists():
                    lcca.unlink()

            # Remove backup copies outside the lock - no concurrent writer can create them
            for path in (bak, ebak):
                if path.exists():
                    try:
                        path.unlink()
                    except Exception as e:
                        self._log(f"delete_chunk: could not remove {path.name}: {e}")

            # Remove WAL entry so crash-replay can't resurrect the chunk on next open
            self._wal_remove(chunk_name)

            # Prune manifest so integrity check never re-flags it as missing
            manifest = self._load_manifest()
            manifest.get("chunks", {}).pop(chunk_name, None)
            self._save_manifest(manifest)

            self._session_dirty = True
            self._log(f"Chunk deleted: '{chunk_name}'.")
            return True

        except Exception as e:
            self._handle_error(f"delete_chunk failed for '{chunk_name}': {e}")
            return False

    def get_rollback_options(self, chunk_name: str) -> list[dict]:
        """
        Returns available rollback copies for a chunk with timestamps.
        Used by UI to show user their options.
        """
        options = []

        lcca = self.chunks_path / f"{chunk_name}{LCCA_EXT}"
        bak = self.chunks_bak_path / f"{chunk_name}{BAK_EXT}"
        ebak = self.chunks_bak_path / f"{chunk_name}{EBAK_EXT}"

        for path, label in [
            (lcca, "Current"),
            (bak, "Previous save"),
            (ebak, "Earlier save"),
        ]:
            if path.exists():
                try:
                    mtime = path.stat().st_mtime
                    _decode(path.read_bytes())  # verify decodable
                    options.append(
                        {
                            "label": label,
                            "file": path.name,
                            "path": str(path),
                            "saved_at": time.strftime(
                                "%Y-%m-%d %H:%M:%S", time.localtime(mtime)
                            ),
                            "readable": self.readable,
                        }
                    )
                except Exception:
                    options.append(
                        {
                            "label": label,
                            "file": path.name,
                            "path": str(path),
                            "saved_at": "unknown",
                            "readable": False,
                        }
                    )

        return options

    def rollback_chunk(self, chunk_name: str, source_path: str) -> bool:
        """
        Rolls back a chunk to a specific copy (by file path).
        source_path must be one of the paths returned by get_rollback_options().
        """
        src = Path(source_path)
        lcca = self.chunks_path / f"{chunk_name}{LCCA_EXT}"

        if not src.exists():
            self._log(f"Rollback source not found: {source_path}")
            return False

        try:
            _decode(src.read_bytes())  # verify source is decodable
            shutil.copy2(src, lcca)
            # Clear staged data for this chunk so next read gets rolled-back version
            with self._write_lock:
                self._staged_data.pop(chunk_name, None)
            self._log(f"Rolled back {chunk_name} from {src.name}.")
            return True
        except Exception as e:
            self._log(f"Rollback failed for {chunk_name}: {e}")
            return False

    # --------------------------------------------------------------------------
    # BLOB STORAGE  (binary files: images, PDFs, ZIPs, etc.)
    # No WAL, no memory staging, no deep copy - streamed directly to disk.
    # No backup copies - blobs are uploaded once and re-uploaded if lost.
    # Checkpoint stores blob hashes only - not the blobs themselves.
    # --------------------------------------------------------------------------

    def _load_blob_manifest(self) -> dict:
        if not self.blob_manifest_path.exists():
            self._log(
                "WARNING: blob_manifest.json is missing. "
                "Blob integrity check will be skipped this session. "
                "Hashes will be rebuilt on next clean close."
            )
            return {"blobs": {}}
        manifest = self._read_admin(self.blob_manifest_path, default={"blobs": {}})
        if manifest.pop("_corrupted", False):
            self._log(
                "WARNING: blob_manifest.json is corrupt. "
                "Blob integrity check will recompute hashes from disk."
            )
            return {"blobs": {}}
        return manifest

    def _update_blob_manifest_hashes(self):
        """Recomputes SHA256 of every .blob file and writes blob_manifest.json."""
        manifest = self._load_blob_manifest()
        blobs = manifest.get("blobs", {})

        # Prune entries for blobs no longer on disk.
        existing = {
            f.name[: -len(BLOB_EXT)] for f in self.blobs_path.glob(f"*{BLOB_EXT}")
        }
        for stale in [k for k in list(blobs) if k not in existing]:
            del blobs[stale]
            self._log(f"Blob manifest: removed stale entry for missing blob '{stale}'.")

        for blob_file in self.blobs_path.glob(f"*{BLOB_EXT}"):
            blob_name = blob_file.name[: -len(BLOB_EXT)]
            try:
                file_hash = hashlib.sha256(blob_file.read_bytes()).hexdigest()
                blobs[blob_name] = {
                    "hash": file_hash,
                    "size": blob_file.stat().st_size,
                    "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            except Exception as e:
                self._log(f"Blob hash failed for {blob_name}: {e}")

        manifest["blobs"] = blobs
        manifest["project_id"] = self.project_id
        manifest["engine_version"] = self.VERSION
        manifest["hashes_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._write_admin(self.blob_manifest_path, manifest)
        self._log("Blob manifest hashes updated.")

    def _verify_blobs(self) -> list[str]:
        """
        Verifies each .blob file against stored SHA256 in blob_manifest.json.
        Returns list of blob names that failed - empty list means all good.
        """
        manifest = self._load_blob_manifest()
        blobs = manifest.get("blobs", {})
        damaged = []

        for blob_name, info in blobs.items():
            if not isinstance(info, dict):
                continue
            stored_hash = info.get("hash")
            if not stored_hash:
                continue
            blob_file = self.blobs_path / f"{blob_name}{BLOB_EXT}"
            if not blob_file.exists():
                damaged.append(blob_name)
                continue
            try:
                if hashlib.sha256(blob_file.read_bytes()).hexdigest() != stored_hash:
                    damaged.append(blob_name)
            except Exception:
                damaged.append(blob_name)

        return damaged

    @requires_active
    def store_blob(
        self,
        data: bytes | str | Path,
        blob_name: str = None,
        overwrite: bool = False,
    ) -> str | None:
        """
        Stores a binary file (image, PDF, ZIP, etc.) as a managed blob.

        data can be:
          - bytes        - raw binary data (blob_name required)
          - str / Path   - path to a file on disk (streamed, never fully loaded)

        blob_name (optional):
          - If omitted and data is a path, the filename is used automatically.
            e.g. store_blob("docs/2024_report.pdf") → blob_name = "2024_report.pdf"
          - If omitted and data is bytes, raises an error (no filename to derive from).
          - Collision handling depends on overwrite flag (see below).

        overwrite=False (default):
          - If blob_name already exists, auto-increments to avoid collision.
            e.g. "report.pdf" → "report_1.pdf" → "report_2.pdf"
          - The final stored name is always returned so caller knows what was used.
        overwrite=True:
          - Replaces existing blob with the same name.

        Writes directly to disk with atomic tmp → fsync → rename.
        No WAL, no memory staging, no deep copy.

        Returns the final blob_name it was stored under on success, None on failure.
        """
        # ── Derive blob_name from path if not provided ────────────────────────
        if not blob_name:
            if isinstance(data, (str, Path)):
                blob_name = Path(data).name
            else:
                self._handle_error(
                    "store_blob: blob_name is required when data is bytes "
                    "(no filename to derive from)."
                )
                return None

        blob_name = blob_name.strip()
        if not self._safe_name(blob_name):
            self._handle_error(
                f"store_blob: rejected unsafe blob_name: {blob_name!r}. "
                "Name must not contain path separators or '..'."
            )
            return None

        # ── Collision handling ────────────────────────────────────────────────
        if not overwrite:
            # Auto-increment: "report.pdf" → "report_1.pdf" → "report_2.pdf"
            stem = Path(blob_name).stem
            suffix = Path(blob_name).suffix  # e.g. ".pdf"
            candidate = blob_name
            counter = 1
            while (self.blobs_path / f"{candidate}{BLOB_EXT}").exists():
                candidate = f"{stem}_{counter}{suffix}"
                counter += 1
            if candidate != blob_name:
                self._log(
                    f"Blob '{blob_name}' already exists - "
                    f"storing as '{candidate}' instead."
                )
            blob_name = candidate

        blob_file = self.blobs_path / f"{blob_name}{BLOB_EXT}"
        tmp = self.blobs_path / f"{blob_name}.tmp"

        try:
            # Stream from path or write from bytes - atomic tmp → fsync → rename
            if isinstance(data, (str, Path)):
                src = Path(data)
                if not src.exists():
                    self._handle_error(f"store_blob: source file not found: {src}")
                    return None
                shutil.copy2(src, tmp)
                with open(tmp, "rb") as f:
                    os.fsync(f.fileno())
            else:
                with open(tmp, "wb") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())

            tmp.replace(blob_file)
            self._session_dirty = True
            self._log(
                f"Blob stored: '{blob_name}' "
                f"({blob_file.stat().st_size / 1024:.1f} KB)."
            )
            return blob_name

        except Exception as e:
            try:
                tmp.unlink()
            except Exception:
                pass
            self._handle_error(f"store_blob failed for '{blob_name}': {e}")
            return None

    @requires_active
    def fetch_blob(self, blob_name: str) -> bytes | None:
        """
        Returns raw bytes for a stored blob.
        Returns None and fires on_fault if the blob is missing or unreadable.
        """
        if not self._safe_name(blob_name):
            self._handle_error(f"fetch_blob: rejected unsafe blob_name: {blob_name!r}")
            return None
        blob_file = self.blobs_path / f"{blob_name}{BLOB_EXT}"

        if not blob_file.exists():
            self._handle_error(
                f"Blob '{blob_name}' not found. "
                f"It may have been deleted or never uploaded."
            )
            return None
        try:
            return blob_file.read_bytes()
        except Exception as e:
            self._handle_error(
                f"Blob '{blob_name}' could not be read: {e}. "
                f"The file may be corrupt - re-upload it."
            )
            return None

    @requires_active
    def delete_blob(self, blob_name: str) -> bool:
        """
        Deletes a blob from disk and removes its entry from blob_manifest.json.
        Returns True on success, False if blob did not exist or deletion failed.
        """
        if not self._safe_name(blob_name):
            self._log(f"delete_blob: rejected unsafe blob_name: {blob_name!r}")
            return False
        blob_file = self.blobs_path / f"{blob_name}{BLOB_EXT}"

        if not blob_file.exists():
            self._log(f"delete_blob: '{blob_name}' not found.")
            return False

        try:
            blob_file.unlink()

            # Remove from manifest
            manifest = self._load_blob_manifest()
            manifest.get("blobs", {}).pop(blob_name, None)
            self._write_admin(self.blob_manifest_path, manifest)

            self._session_dirty = True
            self._log(f"Blob deleted: '{blob_name}'.")
            return True

        except Exception as e:
            self._handle_error(f"delete_blob failed for '{blob_name}': {e}")
            return False

    @requires_active
    def list_blobs(self) -> list[dict]:
        """
        Returns metadata for all stored blobs.
        Includes name, size_kb, and saved_at from manifest.
        """
        manifest = self._load_blob_manifest()
        stored = manifest.get("blobs", {})
        results = []

        for blob_file in sorted(self.blobs_path.glob(f"*{BLOB_EXT}")):
            blob_name = blob_file.name[: -len(BLOB_EXT)]
            info = stored.get(blob_name, {})
            try:
                size = blob_file.stat().st_size
            except Exception:
                size = 0
            results.append(
                {
                    "blob_name": blob_name,
                    "size_kb": round(size / 1024, 1),
                    "saved_at": info.get("saved_at", "unknown"),
                }
            )

        return results

    # --------------------------------------------------------------------------
    # PROJECT MANAGEMENT
    # --------------------------------------------------------------------------

    def rename(self, new_display_name: str) -> bool:
        if not new_display_name.strip():
            return False
        self.display_name = new_display_name.strip()
        try:
            existing = self._read_admin(self.version_path)
            existing["display_name"] = self.display_name
            self._write_admin(self.version_path, existing)
            self._log(f"Renamed to '{self.display_name}'.")
            return True
        except Exception as e:
            self._handle_error(f"Rename failed: {e}")
            return False

    def write_user_meta(self, key: str, value) -> bool:
        """
        Writes a single key-value pair to project_meta.json.
        project_meta.json is always plain JSON and is the right place for
        any app-level or user-level flags/notes (e.g. "fit_for_comparison",
        custom tags, author notes). Keys are arbitrary strings; values must
        be JSON-serialisable. Existing keys are preserved.
        """
        try:
            existing = self._read_admin(self.project_meta_path)
            existing[key] = value
            self._write_admin(self.project_meta_path, existing)
            self._log(f"user_meta['{key}'] set to {value!r}.")
            return True
        except Exception as e:
            self._handle_error(f"write_user_meta failed for '{key}': {e}")
            return False

    def read_user_meta(self, key: str, default=None):
        """
        Reads a single key from project_meta.json.
        Returns default if the key is absent or the file does not exist.
        """
        return self._read_admin(self.project_meta_path).get(key, default)

    def delete_project(self, confirmed: bool = False) -> bool:
        if not confirmed:
            return False
        try:
            self.detach()
            if self.project_path.exists():
                shutil.rmtree(self.project_path)
            return True
        except Exception as e:
            self._handle_error(f"Delete failed: {e}")
            return False

    # --------------------------------------------------------------------------
    # FACTORY METHODS
    # --------------------------------------------------------------------------

    @classmethod
    def new(
        cls,
        project_id: str = None,
        display_name: str = None,
        base_dir: str = None,
        readable: bool = False,
        **kwargs,
    ):
        """Creates a new project with a unique folder."""
        if base_dir is None:
            base_dir = cls.get_default_base_dir()
        
        root = Path(base_dir)
        root.mkdir(parents=True, exist_ok=True)

        base_name = project_id or "new_project"
        target_id = base_name
        counter = 1
        while (root / target_id).exists():
            target_id = f"{base_name}_{counter}"
            counter += 1

        try:
            instance = cls(
                target_id,
                display_name=display_name,
                base_dir=str(root),
                readable=readable,
                **kwargs,
            )
            return instance, "SUCCESS"
        except Exception as e:
            return None, f"FAILED_TO_CREATE: {e}"

    @classmethod
    def open(cls, project_id, base_dir=None, readable=False, **kwargs):
        if base_dir is None:
            base_dir = cls.get_default_base_dir()
            
        root = Path(base_dir)
        if not (root / project_id).exists():
            return None, "PROJECT_NOT_FOUND"

        lock = root / project_id / ".lock"
        if lock.exists() and not cls._is_lock_live(lock):
            try:
                lock.unlink()
            except Exception:
                pass

        # Always read readable mode from version.json to honour the project's stored setting.
        vf = root / project_id / "version.json"
        readable = cls._read_admin(vf).get("readable", False)

        try:
            instance = cls(
                project_id,
                base_dir=str(root),
                readable=readable,
                **kwargs,
            )
            if not instance.is_active():
                return None, "PROJECT_ALREADY_OPEN"
            return instance, "SUCCESS"
        except Exception as e:
            return None, f"OPEN_ERROR: {e}"

    # --------------------------------------------------------------------------
    # STATIC HELPERS
    # --------------------------------------------------------------------------

    @staticmethod
    def list_all_projects(base_dir: str = None) -> list[dict]:
        """
        Lightweight scan - reads only version.json and filesystem metadata.
        Safe to call frequently from the home screen.
        """
        if base_dir is None:
            base_dir = SafeChunkEngine.get_default_base_dir()
            
        root = Path(base_dir)
        if not root.exists():
            return []

        results = []
        for item in root.iterdir():
            if not item.is_dir():
                continue
            if not (item / "chunks").exists():
                continue

            info = {
                "project_id": item.name,
                "display_name": item.name,
                "created_at": None,
                "last_modified": None,
                "status": "ok",
                "user_meta": {},
                "project_path": str(item),
            }

            # Lock status
            lock = item / ".lock"
            if lock.exists() and SafeChunkEngine._is_lock_live(lock):
                info["status"] = "locked"

            # version.json
            vf = item / "version.json"
            if vf.exists():
                data = SafeChunkEngine._read_admin(vf)
                if data:
                    name = data.get("display_name", "").strip()
                    if name and name != item.name:
                        info["display_name"] = name
                    if not data.get("clean_close", True) and info["status"] == "ok":
                        info["status"] = "crashed"
                else:
                    info["status"] = "corrupted"

            # project_meta.json - app/user metadata (always plain JSON)
            pm = item / "project_meta.json"
            if pm.exists():
                info["user_meta"] = SafeChunkEngine._read_admin(pm)

            # Timestamps
            try:
                st = item.stat()
                info["created_at"] = time.strftime(
                    "%Y-%m-%d %H:%M", time.localtime(st.st_ctime)
                )
                info["last_modified"] = time.strftime(
                    "%Y-%m-%d %H:%M", time.localtime(st.st_mtime)
                )
            except Exception:
                pass

            results.append(info)

        return results

    @staticmethod
    def get_project_info(
        project_id: str,
        base_dir: str = None,
    ) -> dict | None:
        """Deep scan of a single project for the detail/info panel."""
        if base_dir is None:
            base_dir = SafeChunkEngine.get_default_base_dir()
            
        root = Path(base_dir)
        item = root / project_id
        if not item.exists():
            return None

        info = {
            "project_id": project_id,
            "display_name": project_id,
            "status": "ok",
            "created_at": None,
            "last_modified": None,
            "app_version": None,
            "engine_version": None,
            "chunk_count": 0,
            "checkpoint_count": 0,
            "last_checkpoint_date": None,
            "clean_close": True,
            "readable": False,
            "user_meta": {},
            "size_kb": 0,
            "project_path": str(item),
        }

        vf = item / "version.json"
        data = SafeChunkEngine._read_admin(vf)
        if data:
            info["display_name"] = data.get("display_name", project_id)
            info["app_version"] = data.get("app_version")
            info["engine_version"] = data.get("engine_version")
            info["clean_close"] = data.get("clean_close", True)
            info["readable"] = data.get("readable", False)
            if not info["clean_close"]:
                info["status"] = "crashed"
        elif vf.exists():
            info["status"] = "corrupted"

        pm = item / "project_meta.json"
        if pm.exists():
            info["user_meta"] = SafeChunkEngine._read_admin(pm)

        lock = item / ".lock"
        if lock.exists() and SafeChunkEngine._is_lock_live(lock):
            info["status"] = "locked"

        chunks_path = item / "chunks"
        if chunks_path.exists():
            info["chunk_count"] = len(list(chunks_path.glob("*.lcca")))

        cp_path = item / "checkpoints"
        if cp_path.exists():
            zips = sorted(
                list((cp_path / "manual").glob("cp_*.3ps"))
                + list((cp_path / "auto").glob("cp_*.3ps")),
                key=os.path.getmtime,
                reverse=True,
            )
            info["checkpoint_count"] = len(zips)
            if zips:
                info["last_checkpoint_date"] = time.strftime(
                    "%Y-%m-%d %H:%M",
                    time.localtime(os.path.getmtime(zips[0])),
                )

        try:
            info["size_kb"] = round(
                sum(f.stat().st_size for f in item.rglob("*") if f.is_file()) / 1024,
                1,
            )
        except Exception:
            pass

        try:
            st = item.stat()
            info["created_at"] = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(st.st_ctime)
            )
            info["last_modified"] = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(st.st_mtime)
            )
        except Exception:
            pass

        return info

    # --------------------------------------------------------------------------
    # DIAGNOSTICS
    # --------------------------------------------------------------------------

    def get_health_report(self) -> dict:
        return {
            "active": self._engine_active,
            "project_id": self.project_id,
            "display_name": self.display_name,
            "version": self.VERSION,
            "app_version": self.app_version,
            "readable_mode": self.readable,
            "optimize": self.optimize,
            "chunk_count": len(list(self.chunks_path.glob(f"*{LCCA_EXT}"))),
            "checkpoint_count": (
                len(list(self.checkpoint_manual.glob("cp_*.3ps")))
                + len(list(self.checkpoint_auto.glob("cp_*.3ps")))
            ),
            "pending_syncs": len(self._staged_data),
            "wal_exists": self.wal_path.exists(),
            "session_dirty": self._session_dirty,
        }

    # --------------------------------------------------------------------------
    # INTERNAL HELPERS
    # --------------------------------------------------------------------------

    @staticmethod
    def _safe_name(name: str) -> bool:
        """
        Returns True if name is safe to use as a filename component.
        Rejects empty strings, path separators, and traversal sequences.
        """
        if not name or not name.strip():
            return False
        p = Path(name)
        # Must be a plain filename - no directory components
        if p.name != name:
            return False
        # Reject traversal sequences explicitly
        if ".." in name:
            return False
        return True

    def _log(self, message: str):
        msg = f"[{time.strftime('%H:%M:%S')}] {message}"
        self.log_history.append(msg)
        if len(self.log_history) > 100:
            self.log_history.pop(0)
        if self.on_status:
            self.on_status(message)
        else:
            print(msg)

    def _handle_error(self, message: str):
        self._log(f"FAULT: {message}")
        if self.on_fault:
            self.on_fault(message)
            