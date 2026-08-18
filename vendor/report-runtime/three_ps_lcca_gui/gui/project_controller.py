from PySide6.QtCore import QObject, Signal, QTimer
from three_ps_lcca_gui.core.safechunk_engine import SafeChunkEngine


class ProjectController(QObject):
    """
    Central mediator between the SafeChunkEngine and the UI.
    """

    status_message = Signal(str)
    sync_completed = Signal()
    fault_occurred = Signal(str)
    dirty_changed = Signal(bool)
    project_loaded = Signal()
    chunk_updated = Signal(str)
    material_trashed = Signal(str)   # emits the material UUID when moved to trash

    def __init__(self):
        super().__init__()
        self.engine = None
        self.active_project_id = None
        self.active_display_name = None
        self._chunk_cache: dict = {}

    # --------------------------------------------------------------------------
    # PROJECT LIFECYCLE
    # --------------------------------------------------------------------------

    def init_project(
        self,
        project_id: str,
        is_new: bool = False,
        display_name: str = None, # type: ignore
    ) -> bool:
        if self.engine:
            self.close_project()

        if is_new:
            self.engine, status = SafeChunkEngine.new(
                project_id,
                display_name=display_name,
                readable=False,
            )
        else:
            self.engine, status = SafeChunkEngine.open(project_id)

        if self.engine and self.engine.is_active():
            self.active_project_id = self.engine.project_id
            self.active_display_name = self.engine.display_name

            self.engine.on_sync = lambda: self.sync_completed.emit()
            self.engine.on_status = lambda msg: self.status_message.emit(msg)
            self.engine.on_fault = lambda msg: self.fault_occurred.emit(msg)
            self.engine.on_dirty = lambda dirty: self.dirty_changed.emit(dirty)

            if is_new:
                self.engine.create_checkpoint(
                    label="initial",
                    notes="Project created.",
                )

            QTimer.singleShot(0, self.project_loaded.emit)
            return True

        return False

    def close_project(self):
        """Force-syncs and detaches the engine cleanly."""
        if self.engine:
            try:
                self.engine.force_sync()
                self.engine.detach()
            except Exception as e:
                self.fault_occurred.emit(f"Error during close: {e}")
            finally:
                self.engine = None
                self.active_project_id = None
                self.active_display_name = None
                self._chunk_cache.clear()
                self.dirty_changed.emit(False)

    # --------------------------------------------------------------------------
    # DATA
    # --------------------------------------------------------------------------

    def save_chunk_data(self, chunk_name: str, data: dict):
        """Passes data to the engine's staging area (debounced write)."""
        if self.engine and self.engine.is_active():
            self._chunk_cache[chunk_name] = data
            self.engine.stage_update(data, chunk_name)
            self.chunk_updated.emit(chunk_name)

    def get_chunk(self, chunk_name: str) -> dict:
        """Returns chunk data - from cache if available, otherwise reads engine."""
        if not self.engine or not self.engine.is_active():
            return {}
        if chunk_name not in self._chunk_cache:
            self._chunk_cache[chunk_name] = self.engine.fetch_chunk(chunk_name)
        return self._chunk_cache[chunk_name]

    def get_fresh_chunk(self, chunk_name: str) -> dict:
        """Force-flushes staged data to disk then reads the chunk from file.

        Ensures any engine.stage_update() calls made outside save_chunk_data()
        are committed before reading, so the returned data is always current.
        Also invalidates the controller cache entry for chunk_name.
        """
        if not self.engine or not self.engine.is_active():
            return {}
        self.engine.force_sync()
        self._chunk_cache.pop(chunk_name, None)
        return self.engine.fetch_chunk(chunk_name)

    def is_dirty(self) -> bool:
        return self.engine.is_dirty() if self.engine else False

    # --------------------------------------------------------------------------
    # CHECKPOINTS
    # --------------------------------------------------------------------------

    def save_checkpoint(self, label: str = "manual", notes: str = "") -> str | None:
        """Creates a manual checkpoint."""
        if self.engine and self.engine.is_active():
            return self.engine.create_checkpoint(label=label, notes=notes)
        return None

    def load_checkpoint(self, zip_name: str) -> bool:
        """Restores project from a checkpoint ZIP."""
        if self.engine and self.engine.is_active():
            self.engine.force_sync()
            success = self.engine.restore_checkpoint(zip_name)
            if success:
                self._chunk_cache.clear()
                self.sync_completed.emit()
                self.project_loaded.emit()
            return success
        return False

    def list_checkpoints(self) -> list:
        return self.engine.list_checkpoints() if self.engine else []

    def delete_checkpoint(self, zip_name: str) -> bool:
        if self.engine and self.engine.is_active():
            return self.engine.delete_checkpoint(zip_name)
        return False

    # --------------------------------------------------------------------------
    # ROLLBACK
    # --------------------------------------------------------------------------

    def list_chunks(self) -> list[str]:
        if self.engine and self.engine.is_active():
            return self.engine.list_chunks()
        return []

    def get_rollback_options(self, chunk_name: str) -> list:
        """Returns available rollback copies for a chunk."""
        if self.engine and self.engine.is_active():
            return self.engine.get_rollback_options(chunk_name)
        return []

    def rollback_chunk(self, chunk_name: str, source_path: str) -> bool:
        """Rolls back a chunk to a specific copy."""
        if self.engine and self.engine.is_active():
            success = self.engine.rollback_chunk(chunk_name, source_path)
            if success:
                self._chunk_cache.pop(chunk_name, None)
            return success
        return False

    # --------------------------------------------------------------------------
    # DIAGNOSTICS
    # --------------------------------------------------------------------------

    def get_engine_logs(self) -> list:
        return list(self.engine.log_history) if self.engine else []

    def get_health_report(self) -> dict:
        return self.engine.get_health_report() if self.engine else {}


