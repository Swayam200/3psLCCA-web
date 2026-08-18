from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QGroupBox,
    QSizePolicy,
    QMessageBox,
    QPushButton,
)
from PySide6.QtCore import QTimer
from three_ps_lcca_gui.gui.themes import get_token
from .base_table import StructureTableWidget, _make_msgbox


class TrashTabWidget(QWidget):
    """
    Scans all structural chunks for items where state['in_trash'] is True
    and displays them in categorized tables for restoration.
    """

    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        # (chunk_id, comp_name) → StructureTableWidget; populated by on_refresh
        self._trash_tables: dict[tuple, StructureTableWidget] = {}
        self.layout = QVBoxLayout(self)

        # Header row
        header_row = QHBoxLayout()
        header = QLabel(
            "<b>Trash Bin</b><br>Items here are excluded from all calculations."
        )
        header.setStyleSheet(f"color: {get_token('text_secondary')}; margin-bottom: 10px;")
        self.delete_all_btn = QPushButton("Delete All")
        self.delete_all_btn.setStyleSheet(
            f"QPushButton {{ background-color: {get_token('danger')}; color: white; }}"
            f"QPushButton:disabled {{ background-color: {get_token('danger', 'disabled')}; color: white; }}"
        )
        self.delete_all_btn.clicked.connect(self._delete_all)
        header_row.addWidget(header, 1)
        header_row.addWidget(self.delete_all_btn)
        self.layout.addLayout(header_row)

        # Scroll Area for multiple group boxes
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.scroll.setWidget(self.container)
        self.layout.addWidget(self.scroll)

        # Define the chunks to scan
        self.chunks = [
            "str_foundation",
            "str_sub_structure",
            "str_super_structure",
            "str_misc",
        ]

    def _delete_all(self):
        box = _make_msgbox(
            self, QMessageBox.Critical,
            "Delete All",
            "Permanently delete all items in trash? This cannot be undone.",
        )
        if box.exec() != QMessageBox.Yes:
            return

        if not self.controller or not self.controller.engine:
            return

        for chunk_id in self.chunks:
            data = self.controller.get_fresh_chunk(chunk_id) or {}
            changed = False
            for comp_name in list(data.keys()):
                before = len(data[comp_name])
                data[comp_name] = [
                    item for item in data[comp_name]
                    if not item.get("state", {}).get("in_trash", False)
                ]
                if len(data[comp_name]) != before:
                    changed = True
            if changed:
                self.controller.save_chunk_data(chunk_id, data)

        self.on_refresh()
        main_view = self.window().findChild(QWidget, "StructureTabView")
        if main_view:
            main_view.update_trash_count()

    def on_refresh(self):
        """Clears the view and re-populates based on nested state['in_trash']."""
        self._trash_tables.clear()

        # Clear existing widgets
        for i in reversed(range(self.container_layout.count())):
            widget = self.container_layout.takeAt(i).widget()
            if widget:
                widget.deleteLater()

        if not self.controller or not self.controller.engine:
            return

        has_content = False
        self.delete_all_btn.setEnabled(False)

        for chunk_id in self.chunks:
            data = self.controller.engine.fetch_chunk(chunk_id) or {}

            for comp_name, items in data.items():
                trashed_items = [
                    (idx, item)
                    for idx, item in enumerate(items)
                    if item.get("state", {}).get("in_trash", False)
                ]

                if trashed_items:
                    has_content = True
                    self.delete_all_btn.setEnabled(True)
                    group = QGroupBox(f"Deleted from: {comp_name}")
                    g_layout = QVBoxLayout(group)

                    table = StructureTableWidget(self, comp_name, is_trash_view=True)
                    self._trash_tables[(chunk_id, comp_name)] = table
                    g_layout.addWidget(table)
                    self.container_layout.addWidget(group)

                    for original_idx, item in trashed_items:
                        table.add_row(item, original_idx)

        if not has_content:
            empty_lbl = QLabel("No items in Trash Bin.")
            empty_lbl.setStyleSheet(f"color: {get_token('text_disabled')}; font-style: italic;")
            self.container_layout.addWidget(empty_lbl)

        # Force items to the top
        self.container_layout.addStretch()
        self.container.adjustSize()

    def permanent_delete(self, comp_name, data_index):
        """Permanently remove an item from the data store."""
        for chunk_id in self.chunks:
            data = self.controller.get_fresh_chunk(chunk_id) or {}
            items = data.get(comp_name, [])
            if data_index >= len(items):
                continue
            if not items[data_index].get("state", {}).get("in_trash", False):
                continue

            del data[comp_name][data_index]
            self.controller.save_chunk_data(chunk_id, data)

            table = self._trash_tables.get((chunk_id, comp_name))

            def _do(t=table, di=data_index):
                if t:
                    t.remove_row_by_index(di, reindex=True)
                    if t.rowCount() == 0:
                        self.on_refresh()
                else:
                    self.on_refresh()
                main_view = self.window().findChild(QWidget, "StructureTabView")
                if main_view:
                    main_view.update_trash_count()

            QTimer.singleShot(0, _do)
            return

    def toggle_trash_status(self, comp_name, data_index, should_trash):
        """
        Restores (should_trash=False) or re-trashes (should_trash=True) an item.
        """
        for chunk_id in self.chunks:
            data = self.controller.get_fresh_chunk(chunk_id) or {}

            if comp_name not in data:
                data[comp_name] = []
            if comp_name in data and data_index < len(data[comp_name]):
                item = data[comp_name][data_index]

                # Before restoring, check for an active item with the same name.
                if not should_trash:
                    restoring_name = (
                        item.get("values", {}).get("material_name", "").strip().lower()
                    )
                    active_names = {
                        it.get("values", {}).get("material_name", "").strip().lower()
                        for it in data[comp_name]
                        if not it.get("state", {}).get("in_trash", False)
                    }
                    if restoring_name and restoring_name in active_names:
                        from PySide6.QtWidgets import QMessageBox
                        QMessageBox.warning(
                            self,
                            "Name Conflict",
                            f'A material named "{item.get("values", {}).get("material_name", "")}" '
                            f'already exists in "{comp_name}".\n\n'
                            "Remove or rename the existing material before restoring this one.",
                        )
                        return

                if "state" not in item:
                    item["state"] = {}
                item["state"]["in_trash"] = should_trash
                if not should_trash:
                    item["state"].pop("_transport_snapshot", None)

                self.controller.save_chunk_data(chunk_id, data)

                # When restoring, clear is_deleted from the component registry
                if not should_trash:
                    try:
                        registry = self.controller.engine.fetch_chunk("str_component_registry") or {}
                        comp_meta = registry.get(chunk_id, {}).get(comp_name, {})
                        if comp_meta.get("is_deleted", False):
                            comp_meta["is_deleted"] = False
                            self.controller.engine.stage_update(
                                chunk_name="str_component_registry", data=registry
                            )
                    except Exception:
                        pass

                table = self._trash_tables.get((chunk_id, comp_name))
                item_data = data[comp_name][data_index]

                def _do(t=table, ci=chunk_id, cn=comp_name, di=data_index,
                        st=should_trash, d=data, idata=item_data):
                    if t:
                        t.remove_row_by_index(di)
                        if t.rowCount() == 0:
                            self.on_refresh()
                    else:
                        self.on_refresh()

                    main_view = self.window().findChild(QWidget, "StructureTabView")
                    if main_view:
                        if not st:
                            _CHUNK_TAB = {
                                "str_foundation":     main_view.foundation_tab,
                                "str_sub_structure":  main_view.substructure_tab,
                                "str_super_structure": main_view.superstructure_tab,
                                "str_misc":           main_view.misc_tab,
                            }
                            active_tab = _CHUNK_TAB.get(ci)
                            section_table = active_tab.sections.get(cn) if active_tab else None
                            if section_table:
                                section_table.insert_row_at_position(idata, di)
                                active_tab.data = d
                                active_tab._update_summary()
                            elif active_tab:
                                main_view.refresh_tab_by_chunk(ci)
                        main_view.update_trash_count()

                QTimer.singleShot(0, _do)
                return
