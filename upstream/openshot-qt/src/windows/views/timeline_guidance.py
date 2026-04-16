"""
 @file
 @brief Compact next-step guidance for the earliest timeline edits
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from classes.app import get_app
from classes.query import File, Marker
from windows.views.effect_cards import clip_supports_effect_cards
from windows.views.transition_presets import estimate_beat_interval_seconds, timeline_item_span


def _item_data(item):
    if isinstance(item, dict):
        return item
    data = getattr(item, "data", None)
    return data if isinstance(data, dict) else None


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalized_entries(items):
    entries = []
    for item in items or []:
        data = _item_data(item)
        if isinstance(data, dict):
            entries.append(data)
    return entries


def _real_file_entries(files):
    entries = []
    for file_data in _normalized_entries(files):
        file_id = str(file_data.get("id") or "")
        if file_id.startswith("__genjob__:"):
            continue
        if not file_id:
            continue
        if not str(file_data.get("path") or "").strip() and not str(file_data.get("name") or "").strip():
            continue
        entries.append(file_data)
    return entries


def _file_media_type(file_data):
    if not isinstance(file_data, dict):
        return "video"
    media_type = str(file_data.get("media_type") or "").strip().lower()
    if media_type in ("video", "image", "audio"):
        return media_type
    if file_data.get("has_audio") and not file_data.get("has_video"):
        return "audio"
    return "video"


def _clip_sort_key(clip_data):
    layer = int(_safe_float(clip_data.get("layer", 0)))
    position = _safe_float(clip_data.get("position", 0.0))
    clip_id = str(clip_data.get("id") or "")
    return (layer, position, clip_id)


def _visual_clip_entries(clips):
    return [
        clip_data for clip_data in _normalized_entries(clips)
        if clip_supports_effect_cards(clip_data)
    ]


def _unused_visual_file_ids(files, clips):
    used_file_ids = {
        str(clip_data.get("file_id") or "")
        for clip_data in _normalized_entries(clips)
        if str(clip_data.get("file_id") or "")
    }
    ranked = []
    for file_data in _real_file_entries(files):
        file_id = str(file_data.get("id") or "")
        if file_id in used_file_ids:
            continue
        media_type = _file_media_type(file_data)
        if media_type not in ("video", "image"):
            continue
        rank = 0 if media_type == "video" else 1
        ranked.append((rank, str(file_data.get("name") or ""), file_id))
    ranked.sort()
    return [file_id for _rank, _name, file_id in ranked]


def _find_first_cut_pair(visual_clips):
    visual_clips = sorted(
        [(_item_data(clip) or clip) for clip in (visual_clips or [])],
        key=_clip_sort_key,
    )
    best_pair = None
    best_score = None

    for index, clip_a in enumerate(visual_clips):
        layer_a = int(_safe_float(clip_a.get("layer", 0)))
        left_a, right_a, _duration_a = timeline_item_span(clip_a)
        for clip_b in visual_clips[index + 1:]:
            layer_b = int(_safe_float(clip_b.get("layer", 0)))
            if layer_a != layer_b:
                continue
            left_b, right_b, _duration_b = timeline_item_span(clip_b)
            gap = left_b - right_a
            overlap = min(right_a, right_b) - max(left_a, left_b)
            score = abs(gap) if overlap <= 0.0 else abs(overlap) * 0.25
            if best_pair is None or score < best_score:
                best_pair = {
                    "clip_ids": [str(clip_a.get("id") or ""), str(clip_b.get("id") or "")],
                    "left_clip": clip_a,
                    "right_clip": clip_b,
                    "gap": gap,
                    "overlap": overlap,
                    "join_position": right_a,
                    "overlap_center": max(left_a, left_b) + (max(0.0, overlap) / 2.0),
                }
                best_score = score
            break

    return best_pair


def _marker_positions(markers):
    positions = []
    for marker_data in _normalized_entries(markers):
        try:
            positions.append(float(marker_data.get("position", 0.0)))
        except (TypeError, ValueError):
            continue
    return sorted(set(positions))


def _suggest_second_clip_defaults(clip_data, markers=None, fallback_bpm=120.0):
    left_edge, right_edge, _duration = timeline_item_span(clip_data)
    marker_positions = _marker_positions(markers)
    beat_info = estimate_beat_interval_seconds(
        right_edge,
        marker_positions=marker_positions,
        fallback_bpm=fallback_bpm,
    )
    beat_duration = max(0.0, _safe_float(beat_info.get("beat_duration"), 0.5))
    fallback_overlap = min(0.35, max(0.12, beat_duration * 0.25))
    marker_window = max(fallback_overlap * 2.0, beat_duration * 0.5)
    nearby_markers = [
        position for position in marker_positions
        if left_edge < position < right_edge and (right_edge - position) <= marker_window
    ]

    if nearby_markers:
        start_position = max(nearby_markers)
        source = "marker"
    else:
        start_position = max(left_edge, right_edge - fallback_overlap)
        source = str(beat_info.get("source") or "bpm")

    overlap_duration = max(0.0, right_edge - start_position)
    return {
        "start_position": round(start_position, 6),
        "overlap_duration": round(overlap_duration, 6),
        "track_number": int(_safe_float(clip_data.get("layer", 0))),
        "source": source,
        "beat_info": beat_info,
    }


def build_timeline_guidance_state(files, clips, transitions, markers=None, tr=None):
    """Return a compact next-step guide for the earliest timeline edits."""
    tr = tr or (lambda text: text)
    clip_entries = _normalized_entries(clips)
    transition_entries = _normalized_entries(transitions)
    visual_clips = sorted(_visual_clip_entries(clip_entries), key=_clip_sort_key)

    if transition_entries or not visual_clips or len(visual_clips) > 2:
        return {
            "visible": False,
            "mode": "hidden",
            "headline": "",
            "detail": "",
            "action_key": "",
            "action_label": "",
            "file_ids": [],
            "clip_ids": [],
            "anchor_position": None,
            "start_position": None,
            "track_number": None,
        }

    if len(visual_clips) == 1:
        next_file_ids = _unused_visual_file_ids(files, clip_entries)
        add_defaults = _suggest_second_clip_defaults(visual_clips[0], markers=markers)
        detail_suffix = (
            tr(" It will open near your marker with a small overlap.")
            if add_defaults.get("source") == "marker"
            else tr(" It will open on the same track with a small beat-sized overlap.")
        )
        return {
            "visible": True,
            "mode": "build_handoff",
            "headline": tr("Next move: add the second shot"),
            "detail": (
                tr("Add one more visual clip on the same track. A small overlap will unlock the transition presets.") + detail_suffix
                if next_file_ids
                else tr("Bring in one more visual clip, then overlap it slightly with this one to unlock the transition presets.") + detail_suffix
            ),
            "action_key": "add_next_clip" if next_file_ids else "import_more",
            "action_label": tr("Add Another Clip") if next_file_ids else tr("Import More Clips"),
            "file_ids": next_file_ids[:1],
            "clip_ids": [str(visual_clips[0].get("id") or "")],
            "anchor_position": _safe_float(visual_clips[0].get("position", 0.0)),
            "start_position": add_defaults.get("start_position"),
            "track_number": add_defaults.get("track_number"),
        }

    pair = _find_first_cut_pair(visual_clips)
    if not pair:
        return {
            "visible": True,
            "mode": "align_tracks",
            "headline": tr("Next move: keep both shots on one track"),
            "detail": tr("Put the first two visual clips on the same track so the transition presets can lock onto the cut."),
            "action_key": "",
            "action_label": "",
            "file_ids": [],
            "clip_ids": [str(clip.get("id") or "") for clip in visual_clips[:2]],
            "anchor_position": None,
            "start_position": None,
            "track_number": None,
        }

    overlap = _safe_float(pair.get("overlap"), 0.0)
    if overlap > 0.0:
        return {
            "visible": True,
            "mode": "style_handoff",
            "headline": tr("Next move: style the first cut"),
            "detail": tr("These clips already overlap. Select them and use the transition presets to finish the cut."),
            "action_key": "select_handoff",
            "action_label": tr("Select First Cut"),
            "file_ids": [],
            "clip_ids": list(pair.get("clip_ids") or []),
            "anchor_position": _safe_float(pair.get("overlap_center"), 0.0),
            "start_position": None,
            "track_number": None,
        }

    return {
        "visible": True,
        "mode": "create_handoff",
        "headline": tr("Next move: create the first cut"),
        "detail": tr("Slide the second clip left so it overlaps the first. Then the transition presets will lock onto the cut."),
        "action_key": "select_handoff",
        "action_label": tr("Select First Cut"),
        "file_ids": [],
        "clip_ids": list(pair.get("clip_ids") or []),
        "anchor_position": _safe_float(pair.get("join_position"), 0.0),
        "start_position": None,
        "track_number": None,
    }


class TimelineGuidanceDockPanel(QFrame):
    """Small next-step guide for the first couple of timeline moves."""

    guidance_state_changed = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        tr = getattr(get_app(), "_tr", lambda text: text)

        self._state = {}
        self.setObjectName("timelineGuidanceDockPanel")
        self.setFrameShape(QFrame.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        header = QLabel(f"<strong>{tr('Next Move')}</strong>", self)
        header.setTextFormat(header.textFormat())
        root.addWidget(header)

        self.summary_label = QLabel(self)
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.detail_label = QLabel(self)
        self.detail_label.setWordWrap(True)
        root.addWidget(self.detail_label)

        self.action_button = QPushButton(self)
        self.action_button.setMinimumHeight(36)
        self.action_button.clicked.connect(self._run_action)
        root.addWidget(self.action_button)

        self.note_label = QLabel(
            tr("This guide disappears after the first cut is built."),
            self,
        )
        self.note_label.setWordWrap(True)
        root.addWidget(self.note_label)

        window = getattr(get_app(), "window", None)
        if window:
            if getattr(window, "propertyTableView", None):
                window.propertyTableView.loadProperties.connect(lambda _selection: self.refresh_state())
            window.refreshFilesSignal.connect(self.refresh_state)
            window.SelectionChanged.connect(self.refresh_state)
            window.ProjectSaved.connect(lambda _path: self.refresh_state())

        self.refresh_state()

    def refresh_state(self):
        app = get_app()
        project = getattr(app, "project", None)
        project_data = getattr(project, "_data", {}) if project else {}
        if not isinstance(project_data, dict):
            project_data = {}

        state = build_timeline_guidance_state(
            project_data.get("files") or [],
            project_data.get("clips") or [],
            project_data.get("transitions") or [],
            [marker.data for marker in Marker.filter() if isinstance(getattr(marker, "data", None), dict)],
            tr=app._tr,
        )
        previous_visible = bool(self._state.get("visible"))
        previous_mode = str(self._state.get("mode") or "")
        self._state = state

        if not state.get("visible"):
            self.summary_label.clear()
            self.detail_label.clear()
            self.action_button.hide()
            self.hide()
            if previous_visible or previous_mode != str(state.get("mode") or ""):
                self.guidance_state_changed.emit(False, str(state.get("mode") or ""))
            return

        self.summary_label.setText(str(state.get("headline") or ""))
        self.detail_label.setText(str(state.get("detail") or ""))
        action_label = str(state.get("action_label") or "")
        self.action_button.setText(action_label)
        self.action_button.setVisible(bool(action_label))
        self.show()
        if (not previous_visible) or previous_mode != str(state.get("mode") or ""):
            self.guidance_state_changed.emit(True, str(state.get("mode") or ""))

    def _run_action(self):
        action_key = str(self._state.get("action_key") or "")
        if not action_key:
            return

        window = getattr(get_app(), "window", None)
        if not window:
            return

        if action_key == "import_more":
            window.actionImportFiles_trigger()
        elif action_key == "add_next_clip":
            file_ids = [str(file_id or "") for file_id in self._state.get("file_ids") or [] if str(file_id or "")]
            files = [File.get(id=file_id) for file_id in file_ids]
            files = [file_obj for file_obj in files if file_obj]
            if files and hasattr(window, "open_add_to_timeline_dialog"):
                window.open_add_to_timeline_dialog(
                    files=files,
                    position=self._state.get("start_position"),
                    track_num=self._state.get("track_number"),
                )
        elif action_key == "select_handoff":
            clip_ids = [str(clip_id or "") for clip_id in self._state.get("clip_ids") or [] if str(clip_id or "")]
            window.addSelection("", "", clear_existing=True)
            for clip_id in clip_ids:
                window.addSelection(clip_id, "clip", clear_existing=False)
            anchor_position = self._state.get("anchor_position")
            if anchor_position is not None:
                fps = get_app().project.get("fps")
                fps_float = float(fps["num"]) / float(fps["den"])
                frame = int(round(float(anchor_position) * fps_float)) + 1
                if hasattr(window, "movePlayhead"):
                    window.movePlayhead(max(1, frame))

        self.refresh_state()
