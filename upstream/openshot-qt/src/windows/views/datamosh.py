"""
 @file
 @brief Compact datamosh dock controls
"""

from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from classes.app import get_app
from classes.datamosh_service import (
    DATAMOSH_AMOUNT_DEFAULT_KEY,
    DATAMOSH_AMOUNT_ORDER,
    DATAMOSH_AMOUNT_PRESETS,
    DATAMOSH_PRESET_ORDER,
    DATAMOSH_PRESETS,
    get_persisted_datamosh_amount_key,
    resolve_datamosh_clip_target,
)
from classes.query import Clip
from classes.ui_text import sanitize_ui_text


class DatamoshDockPanel(QFrame):
    """Small preset-first datamosh controls for one selected clip."""

    def __init__(self, parent=None):
        super().__init__(parent)
        tr = getattr(get_app(), "_tr", lambda text: text)

        self._selection = []
        self._clip_id = ""
        self._history_clip_id = ""
        self._amount_key = DATAMOSH_AMOUNT_DEFAULT_KEY
        self.setObjectName("datamoshDockPanel")
        self.setFrameShape(QFrame.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        header = QLabel(f"<strong>{tr('Datamosh')}</strong>", self)
        header.setTextFormat(header.textFormat())
        root.addWidget(header)

        self.summary_label = QLabel(tr("Select one video clip to generate a datamoshed version."), self)
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.status_label = QLabel(tr("The generated clip will be cached and placed above the original."), self)
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        amount_header = QLabel(f"<strong>{tr('Amount')}</strong>", self)
        amount_header.setTextFormat(amount_header.textFormat())
        root.addWidget(amount_header)

        amount_grid = QGridLayout()
        amount_grid.setContentsMargins(0, 0, 0, 0)
        amount_grid.setHorizontalSpacing(6)
        amount_grid.setVerticalSpacing(6)
        self._amount_buttons = {}
        for index, amount_key in enumerate(DATAMOSH_AMOUNT_ORDER):
            amount = DATAMOSH_AMOUNT_PRESETS[amount_key]
            button = QPushButton(tr(amount["label"]), self)
            button.setCheckable(True)
            button.setMinimumHeight(30)
            button.clicked.connect(lambda _checked=False, key=amount_key: self._select_amount(key))
            amount_grid.addWidget(button, 0, index)
            self._amount_buttons[amount_key] = button
        root.addLayout(amount_grid)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self._preset_buttons = {}
        for index, preset_key in enumerate(DATAMOSH_PRESET_ORDER):
            preset = DATAMOSH_PRESETS[preset_key]
            button = QPushButton(
                "{}\n{}".format(tr(preset["label"]), tr(preset["description"])),
                self,
            )
            button.setMinimumHeight(56)
            button.clicked.connect(lambda _checked=False, key=preset_key: self._apply_preset(key))
            button.setToolTip(tr(preset["description"]))
            grid.addWidget(button, index // 2, index % 2)
            self._preset_buttons[preset_key] = button
        root.addLayout(grid)

        self.history_header = QLabel(f"<strong>{tr('Recent Variants')}</strong>", self)
        self.history_header.setTextFormat(self.history_header.textFormat())
        root.addWidget(self.history_header)

        self.history_label = QLabel(
            tr("Recent cached variants will appear here after you generate one."),
            self,
        )
        self.history_label.setWordWrap(True)
        root.addWidget(self.history_label)

        self.history_grid = QGridLayout()
        self.history_grid.setContentsMargins(0, 0, 0, 0)
        self.history_grid.setHorizontalSpacing(6)
        self.history_grid.setVerticalSpacing(6)
        root.addLayout(self.history_grid)
        self._history_buttons = []

        self.note_label = QLabel(
            tr("Datamosh now bakes the selected clip's current edited result before moshing. ")
            + tr("Use the amount row or recent variants to stay in the fast path."),
            self,
        )
        self.note_label.setWordWrap(True)
        root.addWidget(self.note_label)

        window = getattr(get_app(), "window", None)
        if window and getattr(window, "propertyTableView", None):
            window.propertyTableView.loadProperties.connect(self.update_selection)
        service = getattr(window, "datamosh_service", None) if window else None
        if service:
            service.job_updated.connect(self._handle_job_update)

        self._set_preset_controls_enabled(False)
        self._set_history_controls_enabled(False)
        self.hide()

    def _clear_history_buttons(self):
        while self.history_grid.count():
            item = self.history_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._history_buttons = []

    def _set_preset_controls_enabled(self, enabled):
        for button in self._preset_buttons.values():
            button.setEnabled(enabled)
        for button in self._amount_buttons.values():
            button.setEnabled(enabled)

    def _set_history_controls_enabled(self, enabled):
        for button in self._history_buttons:
            button.setEnabled(enabled)

    def _sync_amount_buttons(self):
        for amount_key, button in self._amount_buttons.items():
            button.setChecked(amount_key == self._amount_key)

    def _select_amount(self, amount_key):
        normalized = str(amount_key or DATAMOSH_AMOUNT_DEFAULT_KEY)
        if normalized not in DATAMOSH_AMOUNT_PRESETS:
            normalized = DATAMOSH_AMOUNT_DEFAULT_KEY
        self._amount_key = normalized
        self._sync_amount_buttons()

    def _update_history_buttons(self, entries):
        self._clear_history_buttons()
        tr = get_app()._tr
        entries = [entry for entry in (entries or []) if isinstance(entry, dict)]
        if not entries:
            self.history_header.hide()
            self.history_label.hide()
            return

        self.history_header.show()
        self.history_label.show()
        self.history_label.setText(
            tr("Tap a recent variant to select it again or restore it above the source.")
        )

        for index, entry in enumerate(entries):
            preset_label = str(entry.get("preset_label") or entry.get("preset_key") or tr("Datamosh"))
            amount_key = str(entry.get("amount_key") or DATAMOSH_AMOUNT_DEFAULT_KEY)
            amount_label = str(entry.get("amount_label") or DATAMOSH_AMOUNT_PRESETS.get(amount_key, {}).get("label") or "")
            subtitle = tr("Cached variant")
            if amount_key != DATAMOSH_AMOUNT_DEFAULT_KEY and amount_label:
                subtitle = tr("%(amount)s variant") % {"amount": amount_label}
            button = QPushButton(
                "{}\n{}".format(tr("Show %(preset)s") % {"preset": preset_label}, subtitle),
                self,
            )
            button.setMinimumHeight(44)
            button.clicked.connect(
                lambda _checked=False, history_id=str(entry.get("id") or ""): self._recall_history(history_id)
            )
            button.setToolTip(tr("Select or restore this cached variant."))
            self.history_grid.addWidget(button, index // 2, index % 2)
            self._history_buttons.append(button)

    def refresh_from_current_selection(self):
        window = getattr(get_app(), "window", None)
        selection = list(getattr(window, "selected_items", []) or []) if window else []
        self.update_selection(selection)

    def update_selection(self, selection):
        self._selection = list(selection or [])
        has_clip = any(isinstance(sel, dict) and sel.get("type") == "clip" for sel in self._selection)
        if not has_clip:
            self._clip_id = ""
            self._history_clip_id = ""
            self.summary_label.setText(
                sanitize_ui_text(get_app()._tr("Select one video clip to generate a datamoshed version."))
            )
            self.status_label.setText(
                sanitize_ui_text(get_app()._tr("The generated clip will be cached and placed above the original."))
            )
            self._clear_history_buttons()
            self.history_header.hide()
            self.history_label.hide()
            self._set_preset_controls_enabled(False)
            self._set_history_controls_enabled(False)
            self._sync_amount_buttons()
            self.hide()
            return

        service = getattr(get_app().window, "datamosh_service", None)
        target = resolve_datamosh_clip_target(self._selection, tr=get_app()._tr)
        self._clip_id = str(target.get("clip_id") or "")
        selected_clip_ids = [
            str(sel.get("id") or "")
            for sel in self._selection
            if isinstance(sel, dict) and sel.get("type") == "clip" and sel.get("id")
        ]
        selected_clip_id = selected_clip_ids[0] if len(selected_clip_ids) == 1 else ""
        self._history_clip_id = (
            service.resolve_history_source_clip_id(selected_clip_id)
            if service and selected_clip_id
            else self._clip_id
        )
        selected_clip = Clip.get(id=selected_clip_id) if selected_clip_id else None
        selected_clip_data = selected_clip.data if selected_clip and isinstance(selected_clip.data, dict) else None
        selected_amount_key = get_persisted_datamosh_amount_key(selected_clip_data)
        if selected_amount_key in DATAMOSH_AMOUNT_PRESETS and (
            self._history_clip_id and self._history_clip_id != self._clip_id
        ):
            self._amount_key = selected_amount_key
        history_entries = service.get_clip_history(self._history_clip_id) if service and self._history_clip_id else []
        self.show()
        if target.get("enabled"):
            summary_text = str(target.get("summary") or get_app()._tr("Datamosh presets"))
            status_text = str(
                target.get("message") or get_app()._tr("Pick a preset to generate a datamoshed clip.")
            )
        elif history_entries and self._history_clip_id and self._history_clip_id != self._clip_id:
            source_clip = Clip.get(id=self._history_clip_id)
            source_title = source_clip.title() if source_clip and callable(getattr(source_clip, "title", None)) else ""
            source_title = sanitize_ui_text(source_title)
            summary_text = get_app()._tr("Derived clip - %(title)s") % {
                "title": source_title or get_app()._tr("Datamosh source")
            }
            status_text = get_app()._tr("Browse or restore recent variants for the original source clip.")
        else:
            summary_text = str(target.get("summary") or get_app()._tr("Datamosh presets"))
            status_text = str(
                target.get("message") or get_app()._tr("Pick a preset to generate a datamoshed clip.")
            )
        self.summary_label.setText(sanitize_ui_text(summary_text))
        self.status_label.setText(sanitize_ui_text(status_text))
        self._update_history_buttons(history_entries)
        self._set_preset_controls_enabled(bool(target.get("enabled")))
        self._set_history_controls_enabled(bool(history_entries))
        self._sync_amount_buttons()
        self._apply_service_state()

    def _apply_service_state(self):
        service = getattr(get_app().window, "datamosh_service", None)
        active_clip_id = self._history_clip_id or self._clip_id
        if not service or not active_clip_id:
            return
        state = service.get_clip_state(active_clip_id)
        status = str(state.get("status") or "")
        message = str(state.get("message") or "")
        if message:
            self.status_label.setText(sanitize_ui_text(message))
        controls_enabled = status not in service.ACTIVE_STATES
        self._set_preset_controls_enabled(bool(self._clip_id) and controls_enabled)
        self._set_history_controls_enabled(bool(self._history_buttons) and controls_enabled)

    def _handle_job_update(self, clip_id, _status, message):
        normalized_clip_id = str(clip_id or "")
        if normalized_clip_id not in {self._clip_id, self._history_clip_id}:
            return
        if message:
            self.status_label.setText(sanitize_ui_text(str(message)))
        service = getattr(get_app().window, "datamosh_service", None)
        if service and self._history_clip_id:
            self._update_history_buttons(service.get_clip_history(self._history_clip_id))
        self._apply_service_state()

    def _apply_preset(self, preset_key):
        if not self._clip_id:
            return
        service = getattr(get_app().window, "datamosh_service", None)
        if not service:
            return
        if service.generate_for_clip(self._clip_id, preset_key, amount_key=self._amount_key):
            self._apply_service_state()

    def _recall_history(self, history_id):
        if not self._history_clip_id or not history_id:
            return
        service = getattr(get_app().window, "datamosh_service", None)
        if not service:
            return
        if service.recall_history_entry(self._history_clip_id, history_id):
            self._apply_service_state()
