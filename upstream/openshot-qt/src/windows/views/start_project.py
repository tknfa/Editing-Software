"""
 @file
 @brief Lightweight start-project helpers and dock controls
"""

import os

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout

from classes.app import get_app
from classes.query import File


START_PROJECT_ACTIONS = {
    "import_files": {
        "label": "Import Files",
        "description": "Bring footage into the project",
    },
    "open_project": {
        "label": "Open Project",
        "description": "Pick up an existing edit",
    },
    "add_to_timeline": {
        "label": "Add to Timeline",
        "description": "Place media on the first edit track",
    },
    "import_more": {
        "label": "Import More",
        "description": "Add more footage before cutting",
    },
}
START_PROJECT_MEDIA_ORDER = ("video", "image", "audio")


def _item_data(item):
    if isinstance(item, dict):
        return item
    data = getattr(item, "data", None)
    return data if isinstance(data, dict) else None


def _normalize_selected_file_ids(selected_file_ids):
    normalized = []
    for file_id in selected_file_ids or []:
        text = str(file_id or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _real_project_file_entries(files):
    entries = []
    for item in files or []:
        data = _item_data(item)
        if not isinstance(data, dict):
            continue
        file_id = str(data.get("id") or "")
        if file_id.startswith("__genjob__:"):
            continue
        path = str(data.get("path") or "").strip()
        name = str(data.get("name") or "").strip()
        if not file_id or (not path and not name):
            continue
        entries.append(data)
    return entries


def _file_media_type(file_entry):
    data = _item_data(file_entry)
    if not isinstance(data, dict):
        return "video"
    media_type = str(data.get("media_type") or "").strip().lower()
    if media_type in START_PROJECT_MEDIA_ORDER:
        return media_type
    if data.get("has_audio") and not data.get("has_video"):
        return "audio"
    return "video"


def _group_file_entries(file_entries):
    groups = {media_type: [] for media_type in START_PROJECT_MEDIA_ORDER}
    for entry in file_entries or []:
        groups[_file_media_type(entry)].append(entry)
    return groups


def _preferred_first_file_ids(file_entries):
    groups = _group_file_entries(file_entries)
    for media_type in START_PROJECT_MEDIA_ORDER:
        group = groups.get(media_type) or []
        if group:
            file_id = str(group[0].get("id") or "")
            return [file_id] if file_id else []
    return []


def _selected_file_entries(file_entries, selected_file_ids):
    selected_ids = set(_normalize_selected_file_ids(selected_file_ids))
    return [
        entry for entry in (file_entries or [])
        if str(entry.get("id") or "") in selected_ids
    ]


def _selected_media_types(file_entries):
    return { _file_media_type(entry) for entry in (file_entries or []) }


def _selected_action_label(selected_entries, tr=None):
    tr = tr or (lambda text: text)
    selected_entries = list(selected_entries or [])
    media_types = _selected_media_types(selected_entries)
    count = len(selected_entries)

    if not selected_entries:
        return tr("Add Selected Media to Timeline")
    if media_types == {"video"}:
        return tr("Add Selected Video to Timeline") if count == 1 else tr("Add Selected Videos to Timeline")
    if media_types == {"image"}:
        return tr("Add Selected Image to Timeline") if count == 1 else tr("Add Selected Images to Timeline")
    if media_types == {"audio"}:
        return tr("Add Selected Audio to Timeline") if count == 1 else tr("Add Selected Audio to Timeline")
    if media_types.issubset({"video", "image"}):
        return tr("Add Selected Visuals to Timeline") if count > 1 else tr("Add Selected Visual to Timeline")
    return tr("Add Selected Media to Timeline")


def _preferred_action_label(preferred_entries, tr=None):
    tr = tr or (lambda text: text)
    if not preferred_entries:
        return tr("Add to Timeline")
    media_type = _file_media_type(preferred_entries[0])
    if media_type == "video":
        return tr("Add First Video to Timeline")
    if media_type == "image":
        return tr("Add First Image to Timeline")
    if media_type == "audio":
        return tr("Add First Audio to Timeline")
    return tr("Add First Clip to Timeline")


def _preferred_headline(selected_entries, preferred_entries, tr=None):
    tr = tr or (lambda text: text)
    if selected_entries:
        media_types = _selected_media_types(selected_entries)
        if media_types == {"audio"}:
            return tr("Selected audio is ready for the timeline")
        if media_types.issubset({"video", "image"}):
            return tr("Selected visual media is ready for the timeline")
        return tr("Selected media is ready for the timeline")

    if not preferred_entries:
        return tr("Put your first clip on the timeline")
    media_type = _file_media_type(preferred_entries[0])
    if media_type == "video":
        return tr("Put your first video on the timeline")
    if media_type == "image":
        return tr("Put your first image on the timeline")
    if media_type == "audio":
        return tr("Put your first audio track on the timeline")
    return tr("Put your first clip on the timeline")


def _count_phrase(count, singular, plural, tr=None):
    tr = tr or (lambda text: text)
    word = singular if int(count or 0) == 1 else plural
    return tr("%(count)d %(word)s") % {"count": int(count or 0), "word": tr(word)}


def _selection_phrase(selected_entries, tr=None):
    tr = tr or (lambda text: text)
    selected_entries = list(selected_entries or [])
    count = len(selected_entries)
    media_types = _selected_media_types(selected_entries)

    if count <= 0:
        return ""
    if media_types == {"video"}:
        return _count_phrase(count, "video", "videos", tr=tr)
    if media_types == {"image"}:
        return _count_phrase(count, "image", "images", tr=tr)
    if media_types == {"audio"}:
        return _count_phrase(count, "audio file", "audio files", tr=tr)
    if media_types.issubset({"video", "image"}):
        return _count_phrase(count, "visual", "visuals", tr=tr)
    return _count_phrase(count, "media item", "media items", tr=tr)


def _bin_inventory_phrase(file_entries, tr=None):
    tr = tr or (lambda text: text)
    groups = _group_file_entries(file_entries)
    parts = []
    if groups["video"]:
        parts.append(_count_phrase(len(groups["video"]), "video", "videos", tr=tr))
    if groups["image"]:
        parts.append(_count_phrase(len(groups["image"]), "image", "images", tr=tr))
    if groups["audio"]:
        parts.append(_count_phrase(len(groups["audio"]), "audio file", "audio files", tr=tr))
    if not parts:
        return tr("Bin: nothing imported yet")
    return tr("Bin: %(items)s") % {"items": " | ".join(parts)}


def _inventory_summary(file_entries, selected_entries, tr=None):
    tr = tr or (lambda text: text)
    selected_phrase = _selection_phrase(selected_entries, tr=tr)
    bin_phrase = _bin_inventory_phrase(file_entries, tr=tr)
    if selected_phrase:
        return tr("Selected: %(selected)s | %(bin)s") % {
            "selected": selected_phrase,
            "bin": bin_phrase,
        }
    return bin_phrase


def _ready_detail(file_entries, selected_entries, tr=None):
    tr = tr or (lambda text: text)
    groups = _group_file_entries(file_entries)
    video_count = len(groups["video"])
    image_count = len(groups["image"])
    audio_count = len(groups["audio"])
    visual_count = video_count + image_count

    if selected_entries:
        selected_types = _selected_media_types(selected_entries)
        if selected_types == {"audio"} and visual_count > 0:
            return tr(
                "Audio is selected right now. Add it to the timeline, or click a video or image in Files first if you want to block the cut visually."
            )
        if selected_types == {"audio"}:
            return tr("Selected audio is ready to drop onto the timeline.")
        if selected_types.issubset({"video", "image"}) and audio_count > 0:
            return tr(
                "Selected visual media is ready to start the cut. Audio in the bin can come in after the first visual pass."
            )
        if selected_types.issubset({"video", "image"}):
            return tr("Selected visual media is ready to start the cut.")
        return tr(
            "Selected media includes both picture and sound. Add it together now, then fine-tune the arrangement on the timeline."
        )

    if visual_count > 0 and audio_count > 0:
        if video_count > 0:
            return tr(
                "You have %(visual)s and %(audio)s in the bin. Start with a video clip, then bring the audio bed in when you're ready."
            ) % {
                "visual": _count_phrase(visual_count, "visual item", "visual items", tr=tr),
                "audio": _count_phrase(audio_count, "audio file", "audio files", tr=tr),
            }
        return tr(
            "You have %(images)s and %(audio)s in the bin. Start with a still or image sequence, then layer audio after."
        ) % {
            "images": _count_phrase(image_count, "image", "images", tr=tr),
            "audio": _count_phrase(audio_count, "audio file", "audio files", tr=tr),
        }
    if video_count > 0 and image_count > 0:
        return tr(
            "You have %(videos)s and %(images)s in the bin. Start with a video clip, or pick a still in Files first if you want a graphic-led opening."
        ) % {
            "videos": _count_phrase(video_count, "video", "videos", tr=tr),
            "images": _count_phrase(image_count, "image", "images", tr=tr),
        }
    if video_count > 0:
        return tr(
            "You have %(videos)s in the bin. Add the first one now, or pick a different shot in Files first."
        ) % {
            "videos": _count_phrase(video_count, "video", "videos", tr=tr),
        }
    if image_count > 0:
        return tr(
            "You have %(images)s in the bin. Add the first one now, or pick a different still in Files first."
        ) % {
            "images": _count_phrase(image_count, "image", "images", tr=tr),
        }
    return tr(
        "You have %(audio)s in the bin. Drop the first track onto the timeline now, or pick a different track in Files first."
    ) % {
        "audio": _count_phrase(audio_count, "audio file", "audio files", tr=tr),
    }


def build_start_project_state(project_filepath, files, clips, selected_file_ids=None, tr=None):
    """Return the compact project-start state for the current project."""
    tr = tr or (lambda text: text)
    file_entries = _real_project_file_entries(files)
    clip_entries = [_item_data(clip) for clip in (clips or []) if isinstance(_item_data(clip), dict)]
    clip_count = len(clip_entries)
    file_count = len(file_entries)
    available_file_ids = [str(entry.get("id") or "") for entry in file_entries if str(entry.get("id") or "")]
    selected_file_ids = [
        file_id for file_id in _normalize_selected_file_ids(selected_file_ids)
        if file_id in available_file_ids
    ]
    selected_entries = _selected_file_entries(file_entries, selected_file_ids)
    default_file_ids = selected_file_ids or _preferred_first_file_ids(file_entries)
    default_entries = _selected_file_entries(file_entries, default_file_ids)

    project_name = os.path.splitext(os.path.basename(str(project_filepath or "").strip()))[0]
    if not project_name:
        project_name = tr("Untitled Project")

    if clip_count > 0:
        return {
            "visible": False,
            "mode": "editing",
            "eyebrow": "",
            "headline": "",
            "detail": "",
            "inventory": "",
            "note": "",
            "actions": [],
            "primary_action_key": "",
            "default_file_ids": [],
            "file_count": file_count,
            "clip_count": clip_count,
        }

    if file_count <= 0:
        return {
            "visible": True,
            "mode": "empty",
            "eyebrow": tr("Project: %(project)s") % {"project": project_name},
            "headline": tr("Bring in footage to start the first cut"),
            "detail": tr("Import clips to begin here, or open an existing project if you are picking the edit back up."),
            "inventory": tr("Bin: nothing imported yet"),
            "note": tr("Tip: drag footage straight into the window from Finder anytime."),
            "actions": [
                {
                    "key": "import_files",
                    "label": tr(START_PROJECT_ACTIONS["import_files"]["label"]),
                    "description": tr(START_PROJECT_ACTIONS["import_files"]["description"]),
                    "enabled": True,
                },
                {
                    "key": "open_project",
                    "label": tr(START_PROJECT_ACTIONS["open_project"]["label"]),
                    "description": tr(START_PROJECT_ACTIONS["open_project"]["description"]),
                    "enabled": True,
                },
            ],
            "primary_action_key": "import_files",
            "default_file_ids": [],
            "file_count": 0,
            "clip_count": 0,
        }

    return {
        "visible": True,
        "mode": "ready",
        "eyebrow": tr("Project: %(project)s") % {"project": project_name},
        "headline": _preferred_headline(selected_entries, default_entries, tr=tr),
        "detail": _ready_detail(file_entries, selected_entries, tr=tr),
        "inventory": _inventory_summary(file_entries, selected_entries, tr=tr),
        "note": tr("Tip: this starter strip steps out as soon as the first clip is on the timeline."),
        "actions": [
            {
                "key": "add_to_timeline",
                "label": _selected_action_label(selected_entries, tr=tr) if selected_entries else _preferred_action_label(default_entries, tr=tr),
                "description": tr(START_PROJECT_ACTIONS["add_to_timeline"]["description"]),
                "enabled": bool(default_file_ids),
            },
            {
                "key": "import_more",
                "label": tr(START_PROJECT_ACTIONS["import_more"]["label"]),
                "description": tr(START_PROJECT_ACTIONS["import_more"]["description"]),
                "enabled": True,
            },
            {
                "key": "open_project",
                "label": tr(START_PROJECT_ACTIONS["open_project"]["label"]),
                "description": tr(START_PROJECT_ACTIONS["open_project"]["description"]),
                "enabled": True,
            },
        ],
        "primary_action_key": "add_to_timeline",
        "default_file_ids": default_file_ids,
        "file_count": file_count,
        "clip_count": 0,
    }


class StartProjectDockPanel(QFrame):
    """Small starter strip for new projects and pre-timeline edits."""

    start_state_changed = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        tr = getattr(get_app(), "_tr", lambda text: text)

        self._state = {}
        self.setObjectName("startProjectDockPanel")
        self.setFrameShape(QFrame.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        header = QLabel(f"<strong>{tr('Start Here')}</strong>", self)
        header.setTextFormat(header.textFormat())
        root.addWidget(header)

        self.project_label = QLabel(self)
        self.project_label.setWordWrap(True)
        root.addWidget(self.project_label)

        self.summary_label = QLabel(self)
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.detail_label = QLabel(self)
        self.detail_label.setWordWrap(True)
        root.addWidget(self.detail_label)

        self.inventory_label = QLabel(self)
        self.inventory_label.setWordWrap(True)
        root.addWidget(self.inventory_label)

        self.action_grid = QGridLayout()
        self.action_grid.setContentsMargins(0, 0, 0, 0)
        self.action_grid.setHorizontalSpacing(8)
        self.action_grid.setVerticalSpacing(8)
        root.addLayout(self.action_grid)
        self._action_buttons = {}

        self.note_label = QLabel(
            tr("This starter strip stays out of the way once the edit is actually on the timeline."),
            self,
        )
        self.note_label.setWordWrap(True)
        root.addWidget(self.note_label)

        self._apply_visual_tone()

        window = getattr(get_app(), "window", None)
        if window:
            if getattr(window, "propertyTableView", None):
                window.propertyTableView.loadProperties.connect(lambda _selection: self.refresh_state())
            window.refreshFilesSignal.connect(self.refresh_state)
            window.SelectionChanged.connect(self.refresh_state)
            window.ProjectSaved.connect(lambda _path: self.refresh_state())
            files_model = getattr(window, "files_model", None)
            if files_model:
                files_model.selection_model.selectionChanged.connect(lambda *_args: self.refresh_state())
                files_model.list_selection_model.selectionChanged.connect(lambda *_args: self.refresh_state())

        self.refresh_state()

    def _clear_action_buttons(self):
        while self.action_grid.count():
            item = self.action_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._action_buttons = {}

    def _apply_muted_label_tone(self, label):
        palette = label.palette()
        muted_color = self.palette().color(QPalette.Disabled, QPalette.WindowText)
        palette.setColor(QPalette.WindowText, muted_color)
        label.setPalette(palette)

    def _apply_visual_tone(self):
        summary_font = self.summary_label.font()
        summary_font.setBold(True)
        if summary_font.pointSizeF() > 0:
            summary_font.setPointSizeF(summary_font.pointSizeF() + 1.0)
        self.summary_label.setFont(summary_font)

        for label in (self.project_label, self.inventory_label, self.note_label):
            font = label.font()
            if font.pointSizeF() > 0:
                font.setPointSizeF(max(9.0, font.pointSizeF() - 0.5))
            self._apply_muted_label_tone(label)
            label.setFont(font)

    def _create_action_button(self, action_key, label, description, enabled, primary=False):
        button = QPushButton(label, self)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.setMinimumHeight(40 if primary else 34)
        button.setToolTip(description)
        button.setEnabled(bool(enabled))
        button.setAutoDefault(False)
        if primary and enabled:
            button.setDefault(True)
        button.clicked.connect(lambda _checked=False, key=action_key: self._run_action(key))
        self._action_buttons[action_key] = button
        return button

    def _rebuild_action_buttons(self, actions):
        self._clear_action_buttons()
        actions = [action for action in (actions or []) if isinstance(action, dict)]
        primary_action_key = str(self._state.get("primary_action_key") or "")
        primary_action = None
        for action in actions:
            if str(action.get("key") or "") == primary_action_key:
                primary_action = action
                break

        row = 0
        if primary_action:
            action_key = str(primary_action.get("key") or "")
            button = self._create_action_button(
                action_key,
                str(primary_action.get("label") or action_key),
                str(primary_action.get("description") or ""),
                bool(primary_action.get("enabled")),
                primary=True,
            )
            self.action_grid.addWidget(button, row, 0, 1, 2)
            row += 1

        secondary_actions = [
            action for action in actions
            if str(action.get("key") or "") != primary_action_key
        ]
        for index, action in enumerate(secondary_actions):
            action_key = str(action.get("key") or "")
            button = self._create_action_button(
                action_key,
                str(action.get("label") or action_key),
                str(action.get("description") or ""),
                bool(action.get("enabled")),
            )
            self.action_grid.addWidget(button, row + (index // 2), index % 2)

    def refresh_state(self):
        app = get_app()
        window = getattr(app, "window", None)
        files = app.project.get("files") or []
        clips = app.project.get("clips") or []
        selected_file_ids = window.selected_file_ids() if window and hasattr(window, "selected_file_ids") else []
        state = build_start_project_state(
            getattr(app.project, "current_filepath", ""),
            files,
            clips,
            selected_file_ids=selected_file_ids,
            tr=app._tr,
        )
        previous_visible = bool(self._state.get("visible"))
        previous_mode = str(self._state.get("mode") or "")
        self._state = state

        if not state.get("visible"):
            self._clear_action_buttons()
            self.hide()
            if previous_visible or previous_mode != str(state.get("mode") or ""):
                self.start_state_changed.emit(False, str(state.get("mode") or ""))
            return

        self.project_label.setText(str(state.get("eyebrow") or ""))
        self.project_label.setVisible(bool(state.get("eyebrow")))
        self.summary_label.setText(str(state.get("headline") or ""))
        self.summary_label.setVisible(bool(state.get("headline")))
        self.detail_label.setText(str(state.get("detail") or ""))
        self.detail_label.setVisible(bool(state.get("detail")))
        self.inventory_label.setText(str(state.get("inventory") or ""))
        self.inventory_label.setVisible(bool(state.get("inventory")))
        self.note_label.setText(str(state.get("note") or ""))
        self.note_label.setVisible(bool(state.get("note")))
        self._rebuild_action_buttons(state.get("actions") or [])
        self.show()
        if (not previous_visible) or previous_mode != str(state.get("mode") or ""):
            self.start_state_changed.emit(True, str(state.get("mode") or ""))

    def focus_primary_action(self):
        action_key = str(self._state.get("primary_action_key") or "")
        button = self._action_buttons.get(action_key)
        if button and button.isEnabled() and self.isVisible():
            button.setFocus()
            return True
        return False

    def _run_action(self, action_key):
        window = getattr(get_app(), "window", None)
        if not window:
            return

        if action_key in ("import_files", "import_more"):
            window.actionImportFiles_trigger()
        elif action_key == "open_project":
            window.actionOpen_trigger()
        elif action_key == "add_to_timeline":
            file_ids = [str(file_id or "") for file_id in self._state.get("default_file_ids") or [] if str(file_id or "")]
            files = [File.get(id=file_id) for file_id in file_ids]
            files = [file_obj for file_obj in files if file_obj]
            if files and hasattr(window, "open_add_to_timeline_dialog"):
                window.open_add_to_timeline_dialog(files=files)

        self.refresh_state()
