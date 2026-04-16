"""
 @file
 @brief Compact project FPS controls for the quick-edit workflow
"""

import os

import openshot
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout

from classes import info
from classes.app import get_app


PROJECT_FPS_PRESETS = (
    {"key": "2398", "label": "23.98", "num": 24000, "den": 1001},
    {"key": "24", "label": "24", "num": 24, "den": 1},
    {"key": "25", "label": "25", "num": 25, "den": 1},
    {"key": "2997", "label": "29.97", "num": 30000, "den": 1001},
    {"key": "30", "label": "30", "num": 30, "den": 1},
    {"key": "50", "label": "50", "num": 50, "den": 1},
    {"key": "5994", "label": "59.94", "num": 60000, "den": 1001},
    {"key": "60", "label": "60", "num": 60, "den": 1},
)
PROJECT_FPS_PRESET_LOOKUP = {preset["key"]: dict(preset) for preset in PROJECT_FPS_PRESETS}
PROJECT_FPS_DEFAULT_PRESET_KEY = "30"


def _project_value(project_data, key, default=None):
    if hasattr(project_data, "get") and not isinstance(project_data, dict):
        try:
            value = project_data.get(key)
        except Exception:
            value = default
        return default if value is None else value
    if isinstance(project_data, dict):
        value = project_data.get(key, default)
        return default if value is None else value
    return default


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def format_project_fps_label(num, den):
    num = _safe_int(num, 30)
    den = _safe_int(den, 1) or 1
    fps_value = float(num) / float(den)
    rounded = round(fps_value)
    if abs(fps_value - rounded) < 0.0001:
        return str(int(rounded))
    return f"{fps_value:.2f}".rstrip("0").rstrip(".")


def matching_project_fps_preset_key(fps_data):
    if not isinstance(fps_data, dict):
        return ""
    num = _safe_int(fps_data.get("num"), 0)
    den = _safe_int(fps_data.get("den"), 1) or 1
    for preset in PROJECT_FPS_PRESETS:
        if num == preset["num"] and den == preset["den"]:
            return preset["key"]
    return ""


def build_project_fps_profile_description(project_data, fps_num, fps_den):
    width = _safe_int(_project_value(project_data, "width", 0), 0)
    height = _safe_int(_project_value(project_data, "height", 0), 0)
    display_ratio = _project_value(project_data, "display_ratio", {}) or {}
    pixel_ratio = _project_value(project_data, "pixel_ratio", {}) or {}
    fps_label = format_project_fps_label(fps_num, fps_den)

    parts = [f"{width}x{height}" if width > 0 and height > 0 else "Custom"]
    parts.append(f"{fps_label} fps")

    display_num = _safe_int(display_ratio.get("num"), 0)
    display_den = _safe_int(display_ratio.get("den"), 0)
    if display_num > 0 and display_den > 0:
        parts.append(f"{display_num}:{display_den}")

    pixel_num = _safe_int(pixel_ratio.get("num"), 1)
    pixel_den = _safe_int(pixel_ratio.get("den"), 1)
    if pixel_num > 0 and pixel_den > 0 and (pixel_num != 1 or pixel_den != 1):
        parts.append(f"PAR {pixel_num}:{pixel_den}")

    return "Editing Software " + " | ".join(parts)


def build_project_fps_state(project_data, tr=None):
    tr = tr or (lambda text: text)
    fps_data = _project_value(project_data, "fps", {}) or {}
    num = _safe_int(fps_data.get("num"), 30)
    den = _safe_int(fps_data.get("den"), 1) or 1
    fps_label = format_project_fps_label(num, den)
    preset_key = matching_project_fps_preset_key({"num": num, "den": den})
    width = _safe_int(_project_value(project_data, "width", 0), 0)
    height = _safe_int(_project_value(project_data, "height", 0), 0)

    actions = []
    for preset in PROJECT_FPS_PRESETS:
        actions.append({
            "key": preset["key"],
            "label": preset["label"],
            "num": preset["num"],
            "den": preset["den"],
            "active": preset["key"] == preset_key,
        })

    if preset_key:
        detail = tr(
            "Timeline timing is running at %(fps)s fps for %(width)dx%(height)d. Switching rates snaps the edit to the new frame grid."
        ) % {
            "fps": fps_label,
            "width": width,
            "height": height,
        }
    else:
        detail = tr(
            "This project is using a custom %(fps)s fps rate for %(width)dx%(height)d. Use the quick buttons below or Custom... for any other rate."
        ) % {
            "fps": fps_label,
            "width": width,
            "height": height,
        }

    return {
        "headline": tr("Project FPS: %(fps)s") % {"fps": fps_label},
        "detail": detail,
        "current_label": fps_label,
        "current_preset_key": preset_key,
        "is_custom": not bool(preset_key),
        "actions": actions,
    }


def iter_available_profiles():
    for profile_folder in (info.USER_PROFILES_PATH, info.PROFILES_PATH):
        if not os.path.isdir(profile_folder):
            continue
        for filename in reversed(sorted(os.listdir(profile_folder))):
            profile_path = os.path.join(profile_folder, filename)
            if os.path.isdir(profile_path):
                continue
            try:
                profile = openshot.Profile(profile_path)
            except RuntimeError:
                continue
            profile.path = profile_path
            profile.user_created = profile_folder == info.USER_PROFILES_PATH
            yield profile


def _project_signature(project_data, fps_num=None, fps_den=None):
    fps_data = _project_value(project_data, "fps", {}) or {}
    fps_num = _safe_int(fps_num if fps_num is not None else fps_data.get("num"), 30)
    fps_den = _safe_int(fps_den if fps_den is not None else fps_data.get("den"), 1) or 1
    display_ratio = _project_value(project_data, "display_ratio", {}) or {}
    pixel_ratio = _project_value(project_data, "pixel_ratio", {}) or {}
    return (
        _safe_int(_project_value(project_data, "width", 0), 0),
        _safe_int(_project_value(project_data, "height", 0), 0),
        _safe_int(display_ratio.get("num"), 1),
        _safe_int(display_ratio.get("den"), 1),
        _safe_int(pixel_ratio.get("num"), 1),
        _safe_int(pixel_ratio.get("den"), 1),
        fps_num,
        fps_den,
    )


def _profile_signature(profile):
    return (
        _safe_int(getattr(profile.info, "width", 0), 0),
        _safe_int(getattr(profile.info, "height", 0), 0),
        _safe_int(getattr(profile.info.display_ratio, "num", 1), 1),
        _safe_int(getattr(profile.info.display_ratio, "den", 1), 1),
        _safe_int(getattr(profile.info.pixel_ratio, "num", 1), 1),
        _safe_int(getattr(profile.info.pixel_ratio, "den", 1), 1),
        _safe_int(getattr(profile.info.fps, "num", 30), 30),
        _safe_int(getattr(profile.info.fps, "den", 1), 1),
    )


def find_project_profile_by_description(project_profile):
    project_profile = str(project_profile or "").strip()
    if not project_profile:
        return None
    for profile in iter_available_profiles():
        description = str(getattr(profile.info, "description", "") or "").strip()
        key = ""
        try:
            key = str(profile.Key() or "").strip()
        except Exception:
            key = ""
        if project_profile == description or (key and project_profile == key):
            return profile
    return None


def build_runtime_project_profile(project_data, fps_num=None, fps_den=None, description=None):
    fps_data = _project_value(project_data, "fps", {}) or {}
    base_profile = find_project_profile_by_description(_project_value(project_data, "profile", ""))
    profile = openshot.Profile()
    if base_profile is not None:
        try:
            profile.SetJson(base_profile.Json())
        except Exception:
            profile = openshot.Profile()

    fps_num = _safe_int(fps_num if fps_num is not None else fps_data.get("num"), 30)
    fps_den = _safe_int(fps_den if fps_den is not None else fps_data.get("den"), 1) or 1

    profile.info.description = str(
        description or build_project_fps_profile_description(project_data, fps_num, fps_den)
    )
    profile.info.width = _safe_int(_project_value(project_data, "width", getattr(profile.info, "width", 1280)), 1280)
    profile.info.height = _safe_int(_project_value(project_data, "height", getattr(profile.info, "height", 720)), 720)

    display_ratio = _project_value(project_data, "display_ratio", {}) or {}
    pixel_ratio = _project_value(project_data, "pixel_ratio", {}) or {}
    profile.info.display_ratio.num = _safe_int(display_ratio.get("num"), getattr(profile.info.display_ratio, "num", 16))
    profile.info.display_ratio.den = _safe_int(display_ratio.get("den"), getattr(profile.info.display_ratio, "den", 9)) or 1
    profile.info.pixel_ratio.num = _safe_int(pixel_ratio.get("num"), getattr(profile.info.pixel_ratio, "num", 1))
    profile.info.pixel_ratio.den = _safe_int(pixel_ratio.get("den"), getattr(profile.info.pixel_ratio, "den", 1)) or 1
    profile.info.fps.num = fps_num
    profile.info.fps.den = fps_den
    return profile


def resolve_project_fps_profile(project_data, preset_key):
    preset = PROJECT_FPS_PRESET_LOOKUP.get(str(preset_key or "").strip())
    if not preset:
        raise KeyError(f"Unknown FPS preset: {preset_key}")

    desired_signature = _project_signature(project_data, preset["num"], preset["den"])
    for profile in iter_available_profiles():
        if _profile_signature(profile) == desired_signature:
            return profile, False

    profile = build_runtime_project_profile(
        project_data,
        fps_num=preset["num"],
        fps_den=preset["den"],
    )

    os.makedirs(info.USER_PROFILES_PATH, exist_ok=True)
    profile_path = os.path.join(info.USER_PROFILES_PATH, profile.Key())
    profile.Save(profile_path)
    profile.path = profile_path
    profile.user_created = True
    return profile, True


class ProjectFPSDockPanel(QFrame):
    """Compact project-level FPS chooser for the simplified workflow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        tr = getattr(get_app(), "_tr", lambda text: text)

        self.setObjectName("projectFpsDockPanel")
        self.setFrameShape(QFrame.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        header = QLabel(f"<strong>{tr('Project FPS')}</strong>", self)
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
        for index, preset in enumerate(PROJECT_FPS_PRESETS):
            button = QPushButton(tr(preset["label"]), self)
            button.setMinimumHeight(34)
            button.clicked.connect(lambda _checked=False, key=preset["key"]: self._apply_preset(key))
            grid.addWidget(button, index // 4, index % 4)
            self._preset_buttons[preset["key"]] = button
        root.addLayout(grid)

        self.custom_button = QPushButton(tr("Custom..."), self)
        self.custom_button.setMinimumHeight(34)
        self.custom_button.clicked.connect(self._open_custom)
        root.addWidget(self.custom_button)

        self.more_profiles_button = QPushButton(tr("More Profiles..."), self)
        self.more_profiles_button.setMinimumHeight(34)
        self.more_profiles_button.clicked.connect(self._open_profile_browser)
        root.addWidget(self.more_profiles_button)

        self.note_label = QLabel(
            tr("Use the quick buttons for common frame rates. Custom... opens the full profile editor when you need a different numerator or denominator."),
            self,
        )
        self.note_label.setWordWrap(True)
        root.addWidget(self.note_label)

        window = getattr(get_app(), "window", None)
        if window and getattr(window, "propertyTableView", None):
            window.propertyTableView.loadProperties.connect(lambda _selection: self.refresh_state())
            window.SelectionChanged.connect(self.refresh_state)
            window.ProjectSaved.connect(lambda _path: self.refresh_state())

        self.refresh_state()

    def refresh_state(self):
        project = getattr(get_app(), "project", None)
        if not project:
            return

        state = build_project_fps_state(project, tr=get_app()._tr)
        self.summary_label.setText(str(state.get("headline") or ""))
        self.detail_label.setText(str(state.get("detail") or ""))
        current_key = str(state.get("current_preset_key") or "")
        current_label = str(state.get("current_label") or "")

        for preset in PROJECT_FPS_PRESETS:
            key = preset["key"]
            button = self._preset_buttons.get(key)
            if not button:
                continue
            is_active = key == current_key
            button.setEnabled(not is_active)
            if is_active:
                button.setToolTip(get_app()._tr("Current project rate: %(fps)s fps") % {"fps": current_label})
            else:
                button.setToolTip(get_app()._tr("Set the project to %(fps)s fps") % {"fps": preset["label"]})

    def _apply_preset(self, preset_key):
        window = getattr(get_app(), "window", None)
        if window and hasattr(window, "apply_project_fps_preset"):
            window.apply_project_fps_preset(preset_key)
        self.refresh_state()

    def _open_custom(self):
        window = getattr(get_app(), "window", None)
        if window and hasattr(window, "open_project_fps_customizer"):
            window.open_project_fps_customizer()
        self.refresh_state()

    def _open_profile_browser(self):
        window = getattr(get_app(), "window", None)
        if window and hasattr(window, "actionProfile_trigger"):
            window.actionProfile_trigger()
        self.refresh_state()
