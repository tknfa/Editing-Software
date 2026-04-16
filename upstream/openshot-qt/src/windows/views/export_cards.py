"""
 @file
 @brief Compact export preset cards and dialog helpers
"""

import os

from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout

from classes.app import get_app
from classes.ui_text import sanitize_ui_text


EXPORT_CARD_DEFAULT_KEY = "quick_mp4"
EXPORT_CARD_PRESET_ORDER = (
    EXPORT_CARD_DEFAULT_KEY,
    "hq_mp4",
    "lossless_mp4",
    "audio_mp3",
)
EXPORT_CARD_PRESETS = {
    EXPORT_CARD_DEFAULT_KEY: {
        "label": "Quick MP4",
        "description": "Fast share-ready export",
        "project_type": "All Formats",
        "target_titles": ("MP4 (h.264 videotoolbox)", "MP4 (h.264)"),
        "quality": "Med",
        "filename_suffix": "",
    },
    "hq_mp4": {
        "label": "High MP4",
        "description": "Cleaner H.264 master",
        "project_type": "All Formats",
        "target_titles": ("MP4 (h.264)", "MP4 (h.264 videotoolbox)"),
        "quality": "High",
        "filename_suffix": "high",
    },
    "lossless_mp4": {
        "label": "Lossless MP4",
        "description": "Archive or re-edit master",
        "project_type": "All Formats",
        "target_titles": ("MP4 (h.264) lossless", "MP4 (h.264)"),
        "quality": "High",
        "filename_suffix": "master",
    },
    "audio_mp3": {
        "label": "Audio MP3",
        "description": "Quick music or vocal bounce",
        "project_type": "All Formats",
        "target_titles": ("MP3 (audio only)",),
        "quality": "High",
        "filename_suffix": "audio",
    },
}


def normalize_export_card_preset_key(preset_key):
    normalized = str(preset_key or EXPORT_CARD_DEFAULT_KEY).strip()
    if normalized not in EXPORT_CARD_PRESETS:
        return EXPORT_CARD_DEFAULT_KEY
    return normalized


def export_card_project_title(project_filepath, tr=None):
    tr = tr or (lambda text: text)
    project_filepath = str(project_filepath or "").strip()
    if not project_filepath:
        return sanitize_ui_text(tr("Untitled Project"))
    title = os.path.splitext(os.path.basename(project_filepath))[0] or tr("Untitled Project")
    return sanitize_ui_text(title)


def build_export_card_filename(project_filepath, preset_key, tr=None):
    tr = tr or (lambda text: text)
    preset = EXPORT_CARD_PRESETS[normalize_export_card_preset_key(preset_key)]
    base_name = export_card_project_title(project_filepath, tr=tr)
    suffix = str(preset.get("filename_suffix") or "").strip()
    if not suffix:
        return sanitize_ui_text(base_name)
    return sanitize_ui_text(tr("%(base)s %(suffix)s") % {
        "base": base_name,
        "suffix": tr(suffix),
    })


def choose_export_card_target_title(available_titles, target_titles):
    normalized_titles = [str(title or "").strip() for title in available_titles or []]
    for preferred_title in target_titles or []:
        preferred_text = str(preferred_title or "").strip()
        if preferred_text and preferred_text in normalized_titles:
            return preferred_text
    return normalized_titles[0] if normalized_titles else ""


def build_export_card_summary(project_filepath, export_folder, tr=None):
    tr = tr or (lambda text: text)
    project_title = export_card_project_title(project_filepath, tr=tr)
    export_folder = str(export_folder or "").strip()
    if export_folder:
        detail = tr("Exports will land in %(folder)s.") % {"folder": export_folder}
    else:
        detail = tr("Choose a folder in the full export window when you need to.")
    return {
        "headline": sanitize_ui_text(tr('Ready to export "%(title)s"') % {"title": project_title}),
        "detail": sanitize_ui_text(detail),
    }


def _combo_index_by_text(combo, preferred_texts):
    preferred = [str(text or "").strip() for text in preferred_texts or [] if str(text or "").strip()]
    for preferred_text in preferred:
        for index in range(combo.count()):
            if str(combo.itemText(index) or "").strip() == preferred_text:
                return index
    return -1


def _combo_index_by_data(combo, preferred_values):
    preferred = [str(value or "").strip() for value in preferred_values or [] if str(value or "").strip()]
    for preferred_value in preferred:
        for index in range(combo.count()):
            if str(combo.itemData(index) or "").strip() == preferred_value:
                return index
    return -1


def apply_export_card_preset(dialog, preset_key, tr=None):
    tr = tr or (lambda text: text)
    preset_key = normalize_export_card_preset_key(preset_key)
    preset = EXPORT_CARD_PRESETS[preset_key]

    if hasattr(dialog, "exportTabs"):
        dialog.exportTabs.setCurrentIndex(0)

    project_type_index = _combo_index_by_data(
        dialog.cboSimpleProjectType,
        [tr(preset["project_type"]), preset["project_type"]],
    )
    if project_type_index >= 0:
        dialog.cboSimpleProjectType.setCurrentIndex(project_type_index)

    target_candidates = [tr(title) for title in preset.get("target_titles") or ()]
    target_index = _combo_index_by_text(dialog.cboSimpleTarget, target_candidates)
    if target_index >= 0:
        dialog.cboSimpleTarget.setCurrentIndex(target_index)

    quality_index = _combo_index_by_data(dialog.cboSimpleQuality, [preset.get("quality")])
    if quality_index < 0:
        quality_index = _combo_index_by_text(dialog.cboSimpleQuality, [tr(str(preset.get("quality") or ""))])
    if quality_index >= 0:
        dialog.cboSimpleQuality.setCurrentIndex(quality_index)

    project_filepath = getattr(get_app().project, "current_filepath", "")
    dialog.txtFileName.setText(build_export_card_filename(project_filepath, preset_key, tr=tr))

    export_folder = str(dialog.txtExportFolder.text() or "").strip()
    if not export_folder:
        settings = get_app().get_settings()
        export_folder = settings.getDefaultPath(settings.actionType.EXPORT)
        dialog.txtExportFolder.setText(export_folder)

    dialog.export_button.setText(
        tr("Export %(label)s") % {"label": tr(str(preset.get("label") or ""))}
    )
    dialog._apply_tab_order()
    dialog.export_button.setFocus()

    available_targets = [dialog.cboSimpleTarget.itemText(index) for index in range(dialog.cboSimpleTarget.count())]
    resolved_target = choose_export_card_target_title(available_targets, target_candidates)
    return {
        "preset_key": preset_key,
        "target_title": resolved_target,
        "quality": str(preset.get("quality") or ""),
        "file_name": str(dialog.txtFileName.text() or ""),
    }


class ExportCardDockPanel(QFrame):
    """Compact preset-first export entry point for the quick-edit flow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        tr = getattr(get_app(), "_tr", lambda text: text)

        self.setObjectName("exportCardDockPanel")
        self.setFrameShape(QFrame.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        header = QLabel(f"<strong>{tr('Export')}</strong>", self)
        header.setTextFormat(header.textFormat())
        root.addWidget(header)

        self.summary_label = QLabel(self)
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.detail_label = QLabel(self)
        self.detail_label.setWordWrap(True)
        root.addWidget(self.detail_label)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self._preset_buttons = {}
        for index, preset_key in enumerate(EXPORT_CARD_PRESET_ORDER):
            preset = EXPORT_CARD_PRESETS[preset_key]
            button = QPushButton(
                "{}\n{}".format(tr(preset["label"]), tr(preset["description"])),
                self,
            )
            button.setMinimumHeight(54)
            button.setToolTip(tr(preset["description"]))
            button.clicked.connect(lambda _checked=False, key=preset_key: self._open_preset(key))
            grid.addWidget(button, index // 2, index % 2)
            self._preset_buttons[preset_key] = button
        root.addLayout(grid)

        self.full_export_button = QPushButton(tr("Open Full Export"), self)
        self.full_export_button.setMinimumHeight(34)
        self.full_export_button.clicked.connect(self._open_full_export)
        root.addWidget(self.full_export_button)

        self.note_label = QLabel(
            tr("These presets open the normal export window already filled in, so finishing a cut stays quick without hiding the full controls."),
            self,
        )
        self.note_label.setWordWrap(True)
        root.addWidget(self.note_label)

        window = getattr(get_app(), "window", None)
        if window and getattr(window, "propertyTableView", None):
            window.propertyTableView.loadProperties.connect(lambda _selection: self.refresh_state())
            window.ProjectSaved.connect(lambda _path: self.refresh_state())

        self.refresh_state()

    def refresh_state(self):
        settings = get_app().get_settings()
        project_filepath = getattr(get_app().project, "current_filepath", "")
        export_folder = settings.getDefaultPath(settings.actionType.EXPORT)
        state = build_export_card_summary(project_filepath, export_folder, tr=get_app()._tr)
        self.summary_label.setText(sanitize_ui_text(str(state.get("headline") or "")))
        self.detail_label.setText(sanitize_ui_text(str(state.get("detail") or "")))

    def _open_preset(self, preset_key):
        window = getattr(get_app(), "window", None)
        if window and hasattr(window, "open_export_preset_dialog"):
            window.open_export_preset_dialog(preset_key)
        self.refresh_state()

    def _open_full_export(self):
        window = getattr(get_app(), "window", None)
        if window and hasattr(window, "open_export_preset_dialog"):
            window.open_export_preset_dialog()
        self.refresh_state()
