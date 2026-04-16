"""
 @file
 @brief Preset-first transition helpers and dock controls
"""

from bisect import bisect_left, bisect_right
import os

from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from classes import info
from classes.app import get_app
from classes.query import Clip, Marker, Transition
from classes.waveform import SAMPLES_PER_SECOND as WAVEFORM_SAMPLES_PER_SECOND


TRANSITION_STYLE_ORDER = (
    "shake_cut",
    "whip_push",
    "slam_zoom",
    "glitch_ripple",
    "clean_fade",
)
TRANSITION_STYLE_AMOUNT_DEFAULT_KEY = "default"
TRANSITION_STYLE_AMOUNT_ORDER = (
    "soft",
    TRANSITION_STYLE_AMOUNT_DEFAULT_KEY,
    "hard",
)

TRANSITION_STYLE_PRESETS = {
    "shake_cut": {
        "label": "Jugg Shake",
        "description": "Fast shaky handoff",
        "mask_parts": ("extra", "big_barr_shaking_1.jpg"),
        "contrast": 6.0,
    },
    "whip_push": {
        "label": "Whip Push",
        "description": "Directional smear",
        "mask_parts": ("common", "wipe_left_to_right.svg"),
        "contrast": 2.5,
    },
    "slam_zoom": {
        "label": "Slam Zoom",
        "description": "Blur-heavy impact",
        "mask_parts": ("extra", "blur_left_barr.jpg"),
        "contrast": 5.0,
    },
    "glitch_ripple": {
        "label": "Glitch Ripple",
        "description": "Messy digital bridge",
        "mask_parts": ("extra", "distortion_8.jpg"),
        "contrast": 5.5,
    },
    "clean_fade": {
        "label": "Clean Fade",
        "description": "Simple soft blend",
        "mask_parts": ("common", "fade.svg"),
        "contrast": 3.0,
    },
}
TRANSITION_STYLE_AMOUNT_PRESETS = {
    "soft": {
        "label": "Soft",
        "multiplier": 0.74,
    },
    TRANSITION_STYLE_AMOUNT_DEFAULT_KEY: {
        "label": "Default",
        "multiplier": 1.0,
    },
    "hard": {
        "label": "Hard",
        "multiplier": 1.35,
    },
}
TRANSITION_STYLE_AMOUNT_UI_KEY = "transition_style_amount"

TRANSITION_TIMING_ORDER = (
    "overlap",
    "quarter_beat",
    "half_beat",
    "one_beat",
    "two_beats",
)

TRANSITION_TIMING_PRESETS = {
    "overlap": {
        "label": "Overlap",
        "beats": None,
    },
    "quarter_beat": {
        "label": "1/4 Beat",
        "beats": 0.25,
    },
    "half_beat": {
        "label": "1/2 Beat",
        "beats": 0.5,
    },
    "one_beat": {
        "label": "1 Beat",
        "beats": 1.0,
    },
    "two_beats": {
        "label": "2 Beats",
        "beats": 2.0,
    },
}
TRANSITION_MARKER_HELPER_ORDER = (
    "playhead",
    "cut",
    "find_hit",
    "beat_pair",
    "clear_nearby",
)
TRANSITION_MARKER_HELPERS = {
    "playhead": {
        "label": "Playhead",
        "description": "Drop a marker at the current frame",
    },
    "cut": {
        "label": "Cut",
        "description": "Drop a marker at the selected cut center",
    },
    "find_hit": {
        "label": "Find Hit",
        "description": "Find the strongest nearby transient",
    },
    "beat_pair": {
        "label": "Beat Pair",
        "description": "Drop a one-beat window around the cut",
    },
    "clear_nearby": {
        "label": "Clear Nearby",
        "description": "Remove helper markers around this cut",
    },
}


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _item_data(item):
    if isinstance(item, dict):
        return item
    data = getattr(item, "data", None)
    return data if isinstance(data, dict) else None


def timeline_item_duration_seconds(item_data):
    """Return the visible duration of a timeline clip/transition item."""
    if not isinstance(item_data, dict):
        return 0.0
    start_s = _safe_float(item_data.get("start", 0.0))
    end_s = _safe_float(item_data.get("end", start_s), start_s)
    duration_s = end_s - start_s
    if duration_s <= 0.0:
        duration_s = _safe_float(item_data.get("duration", 0.0))
    return max(0.0, duration_s)


def timeline_item_span(item_data):
    """Return (left, right, duration) for a timeline item."""
    left_edge = _safe_float(item_data.get("position", 0.0))
    duration_s = timeline_item_duration_seconds(item_data)
    return left_edge, left_edge + duration_s, duration_s


def transition_target_center(target):
    """Return the center point of a resolved transition target."""
    if not isinstance(target, dict):
        return 0.0
    left_edge = _safe_float(target.get("position", 0.0))
    duration_s = max(0.0, _safe_float(target.get("duration", 0.0)))
    return left_edge + (duration_s / 2.0)


def _normalize_marker_positions(marker_positions):
    normalized = []
    for value in marker_positions or []:
        try:
            normalized.append(float(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(normalized))


def estimate_beat_interval_seconds(anchor_position, marker_positions=None, fallback_bpm=120.0):
    """Estimate one beat duration from surrounding markers, or fall back to BPM."""
    fallback_bpm = min(240.0, max(40.0, _safe_float(fallback_bpm, 120.0)))
    fallback_duration = 60.0 / fallback_bpm if fallback_bpm > 0.0 else 0.5

    normalized = _normalize_marker_positions(marker_positions)
    anchor_position = float(anchor_position or 0.0)
    left_index = bisect_left(normalized, anchor_position) - 1
    right_index = bisect_right(normalized, anchor_position)
    left_marker = normalized[left_index] if left_index >= 0 else None
    right_marker = normalized[right_index] if right_index < len(normalized) else None

    if left_marker is not None and right_marker is not None:
        gap = right_marker - left_marker
        if 0.15 <= gap <= 3.0:
            return {
                "beat_duration": gap,
                "bpm": 60.0 / gap if gap > 0.0 else fallback_bpm,
                "source": "markers",
                "source_label": "markers around cut",
            }

    return {
        "beat_duration": fallback_duration,
        "bpm": fallback_bpm,
        "source": "bpm",
        "source_label": f"{fallback_bpm:.0f} BPM fallback",
    }


def resolve_transition_overlap_span(transition_data, clip_items):
    """Infer the real clip-overlap span surrounding one transition."""
    if not isinstance(transition_data, dict):
        return None

    transition_layer = int(_safe_float(transition_data.get("layer", 0)))
    tran_left, tran_right, tran_duration = timeline_item_span(transition_data)
    if tran_duration <= 0.0:
        return None
    tran_center = (tran_left + tran_right) / 2.0

    clips = []
    for item in clip_items or []:
        item_data = _item_data(item)
        if not isinstance(item_data, dict):
            continue
        if int(_safe_float(item_data.get("layer", 0))) != transition_layer:
            continue
        left_edge, right_edge, duration_s = timeline_item_span(item_data)
        if duration_s <= 0.0:
            continue
        clips.append((left_edge, right_edge, item_data))

    best_span = None
    best_score = None
    for index, clip_a in enumerate(clips):
        for clip_b in clips[index + 1:]:
            overlap_left = max(clip_a[0], clip_b[0])
            overlap_right = min(clip_a[1], clip_b[1])
            overlap_duration = overlap_right - overlap_left
            if overlap_duration <= 0.0:
                continue
            overlap_center = overlap_left + (overlap_duration / 2.0)
            intersects_transition = min(tran_right, overlap_right) - max(tran_left, overlap_left) > 0.0
            center_in_overlap = overlap_left <= tran_center <= overlap_right
            if not intersects_transition and not center_in_overlap:
                continue
            score = abs(overlap_center - tran_center) + abs(overlap_duration - tran_duration)
            if best_span is None or score < best_score:
                best_span = {
                    "left": overlap_left,
                    "right": overlap_right,
                    "position": overlap_left,
                    "duration": overlap_duration,
                }
                best_score = score

    return best_span


def build_transition_timing_target(
    target,
    timing_key,
    *,
    marker_positions=None,
    fallback_bpm=120.0,
    frame_duration=0.0,
    span_limits=None,
):
    """Return a target resized to a beat-based duration while keeping the same center."""
    if not isinstance(target, dict):
        return None

    timing = TRANSITION_TIMING_PRESETS.get(timing_key) or TRANSITION_TIMING_PRESETS["overlap"]
    result = dict(target)
    result["timing_key"] = timing_key if timing_key in TRANSITION_TIMING_PRESETS else "overlap"
    result["beat_info"] = estimate_beat_interval_seconds(
        transition_target_center(target),
        marker_positions=marker_positions,
        fallback_bpm=fallback_bpm,
    )
    result["requested_duration"] = max(0.0, _safe_float(target.get("duration", 0.0)))

    if timing.get("beats") is None:
        return result

    beat_duration = _safe_float(result["beat_info"].get("beat_duration"), 0.5)
    desired_duration = beat_duration * float(timing["beats"])
    if frame_duration and frame_duration > 0.0:
        desired_duration = max(frame_duration, round(desired_duration / frame_duration) * frame_duration)
    else:
        desired_duration = max(0.0, desired_duration)
    result["requested_duration"] = desired_duration

    center_position = transition_target_center(target)
    max_left = None
    max_right = None
    if isinstance(span_limits, dict):
        try:
            max_left = float(span_limits.get("left"))
            max_right = float(span_limits.get("right"))
        except (TypeError, ValueError):
            max_left = None
            max_right = None
        if max_right is not None and max_left is not None and max_right > max_left:
            desired_duration = min(desired_duration, max_right - max_left)

    desired_duration = max(frame_duration if frame_duration > 0.0 else 0.0, desired_duration)
    left_edge = center_position - (desired_duration / 2.0)
    if max_left is not None and max_right is not None and max_right > max_left:
        left_edge = min(max_right - desired_duration, max(max_left, left_edge))

    result["position"] = left_edge
    result["duration"] = desired_duration
    return result


def describe_transition_timing_target(
    target,
    timing_key,
    *,
    marker_positions=None,
    fallback_bpm=120.0,
    frame_duration=0.0,
    span_limits=None,
    tr=None,
):
    """Build a short human-readable status line for the timing controls."""
    tr = tr or (lambda text: text)
    preview = build_transition_timing_target(
        target,
        timing_key,
        marker_positions=marker_positions,
        fallback_bpm=fallback_bpm,
        frame_duration=frame_duration,
        span_limits=span_limits,
    )
    if not preview:
        return tr("Pick a preset to create or restyle the selected overlap.")

    beat_info = preview.get("beat_info") or {}
    source_label = tr(str(beat_info.get("source_label") or "120 BPM fallback"))
    beat_duration = _safe_float(beat_info.get("beat_duration"), 0.5)
    timing = TRANSITION_TIMING_PRESETS.get(timing_key) or TRANSITION_TIMING_PRESETS["overlap"]

    if timing.get("beats") is None:
        return tr("Beat timing ready - %(source)s - %(beat).3f s per beat") % {
            "source": source_label,
            "beat": beat_duration,
        }

    duration_s = _safe_float(preview.get("duration"), 0.0)
    requested_duration = _safe_float(preview.get("requested_duration"), duration_s)
    if duration_s + 1e-6 < requested_duration:
        return tr("%(label)s - %(duration).3f s (clamped) - %(source)s") % {
            "label": tr(timing["label"]),
            "duration": duration_s,
            "source": source_label,
        }

    return tr("%(label)s - %(duration).3f s - %(source)s") % {
        "label": tr(timing["label"]),
        "duration": duration_s,
        "source": source_label,
    }


def _normalize_transition_marker_positions(values):
    normalized = []
    seen = set()
    for value in values or []:
        try:
            marker_value = float(value)
        except (TypeError, ValueError):
            continue
        rounded = round(marker_value, 6)
        if rounded in seen:
            continue
        seen.add(rounded)
        normalized.append(marker_value)
    return sorted(normalized)


def clip_has_audio_waveform_data(clip_data):
    """Return True when a clip has usable waveform samples for transient search."""
    if not isinstance(clip_data, dict):
        return False
    ui_data = clip_data.get("ui")
    audio_data = ui_data.get("audio_data") if isinstance(ui_data, dict) else None
    if not (isinstance(audio_data, list) and len(audio_data) > 1):
        return False
    reader = clip_data.get("reader")
    if isinstance(reader, dict) and reader.get("has_audio") is False:
        return False
    return True


def clip_has_audio_source(clip_data):
    """Best-effort check for whether a clip carries audio."""
    if not isinstance(clip_data, dict):
        return False
    reader = clip_data.get("reader")
    if not isinstance(reader, dict):
        return False
    has_audio = reader.get("has_audio")
    return True if has_audio is None else bool(has_audio)


def get_transition_transient_search_radius(anchor_position, marker_positions=None, fallback_bpm=120.0):
    beat_info = estimate_beat_interval_seconds(
        anchor_position,
        marker_positions=marker_positions,
        fallback_bpm=fallback_bpm,
    )
    beat_duration = max(0.0, _safe_float(beat_info.get("beat_duration"), 0.5))
    return min(0.45, max(0.12, beat_duration * 0.45))


def find_transition_audio_transient(
    anchor_position,
    clip_items,
    *,
    marker_positions=None,
    fallback_bpm=120.0,
    search_radius=None,
    samples_per_second=WAVEFORM_SAMPLES_PER_SECOND,
):
    """Return the strongest nearby transient marker candidate around an anchor."""
    try:
        anchor_position = float(anchor_position)
    except (TypeError, ValueError):
        return None

    beat_info = estimate_beat_interval_seconds(
        anchor_position,
        marker_positions=marker_positions,
        fallback_bpm=fallback_bpm,
    )
    if search_radius is None:
        search_radius = get_transition_transient_search_radius(
            anchor_position,
            marker_positions=marker_positions,
            fallback_bpm=fallback_bpm,
        )
    search_radius = max(0.05, float(search_radius or 0.0))

    best_candidate = None
    best_score = None
    for item in clip_items or []:
        item_data = _item_data(item)
        if not clip_has_audio_waveform_data(item_data):
            continue

        left_edge, right_edge, duration_s = timeline_item_span(item_data)
        if duration_s <= 0.0:
            continue
        window_left = max(left_edge, anchor_position - search_radius)
        window_right = min(right_edge, anchor_position + search_radius)
        if window_right <= window_left:
            continue

        ui_data = item_data.get("ui") if isinstance(item_data, dict) else None
        audio_data = ui_data.get("audio_data") if isinstance(ui_data, dict) else None
        if not isinstance(audio_data, list) or len(audio_data) < 2:
            continue

        samples = len(audio_data)
        last_index = samples - 1
        start_ratio = (window_left - left_edge) / duration_s
        end_ratio = (window_right - left_edge) / duration_s
        start_index = max(0, min(last_index, int(start_ratio * last_index)))
        end_index = max(start_index, min(last_index, int(end_ratio * last_index) + 1))

        reader = item_data.get("reader") if isinstance(item_data, dict) else None
        has_video = True if not isinstance(reader, dict) or reader.get("has_video") is None else bool(reader.get("has_video"))
        for sample_index in range(start_index, end_index + 1):
            current = abs(_safe_float(audio_data[sample_index], 0.0))
            prev_value = abs(_safe_float(audio_data[max(0, sample_index - 1)], current))
            next_value = abs(_safe_float(audio_data[min(last_index, sample_index + 1)], current))
            rise = max(0.0, current - prev_value)
            local_peak = max(0.0, current - ((prev_value + next_value) / 2.0))
            audio_only_bonus = 0.03 if (not has_video and current > 0.0) else 0.0
            transient_score = (current * 0.7) + (rise * 1.2) + (local_peak * 0.6) + audio_only_bonus
            candidate_position = left_edge + (float(sample_index) / float(last_index)) * duration_s
            score = (
                transient_score,
                -abs(candidate_position - anchor_position),
            )
            if best_candidate is None or score > best_score:
                best_candidate = {
                    "position": candidate_position,
                    "score": transient_score,
                    "anchor_position": anchor_position,
                    "search_radius": search_radius,
                    "beat_info": beat_info,
                }
                best_score = score

    if not best_candidate or _safe_float(best_candidate.get("score"), 0.0) < 0.02:
        return None
    return best_candidate


def build_transition_beat_marker_plan(
    target,
    helper_key,
    *,
    playhead_position=0.0,
    marker_positions=None,
    fallback_bpm=120.0,
    timeline_end=None,
):
    """Return marker positions for a lightweight transition beat-marker helper."""
    helper_key = str(helper_key or "")
    if helper_key not in TRANSITION_MARKER_HELPERS:
        return None

    max_position = None
    try:
        if timeline_end is not None:
            max_position = float(timeline_end)
    except (TypeError, ValueError):
        max_position = None

    def clamp_position(value):
        try:
            position = float(value)
        except (TypeError, ValueError):
            position = 0.0
        position = max(0.0, position)
        if max_position is not None:
            position = min(max_position, position)
        return position

    plan = {
        "helper_key": helper_key,
        "positions": [],
        "anchor_position": None,
        "beat_info": None,
    }

    if helper_key == "playhead":
        plan["anchor_position"] = clamp_position(playhead_position)
        plan["positions"] = [plan["anchor_position"]]
        return plan

    if not isinstance(target, dict) or not target.get("enabled"):
        return None

    anchor_position = clamp_position(transition_target_center(target))
    plan["anchor_position"] = anchor_position

    if helper_key == "cut":
        plan["positions"] = [anchor_position]
        return plan

    beat_info = estimate_beat_interval_seconds(
        anchor_position,
        marker_positions=marker_positions,
        fallback_bpm=fallback_bpm,
    )
    plan["beat_info"] = beat_info
    half_beat = max(0.0, _safe_float(beat_info.get("beat_duration"), 0.5) / 2.0)
    pair_positions = _normalize_transition_marker_positions(
        [
            clamp_position(anchor_position - half_beat),
            clamp_position(anchor_position + half_beat),
        ]
    )

    if helper_key == "beat_pair":
        plan["positions"] = pair_positions
        return plan

    if helper_key == "clear_nearby":
        plan["positions"] = _normalize_transition_marker_positions(pair_positions + [anchor_position])
        return plan

    return None


def get_transition_style_mask_path(preset_key):
    """Return the built-in mask asset path for one transition preset."""
    preset = TRANSITION_STYLE_PRESETS.get(preset_key)
    if not preset:
        return None
    return os.path.join(info.PATH, "transitions", *preset["mask_parts"])


def get_transition_style_preset_key(transition_data):
    """Infer the current transition preset from saved UI or reader metadata."""
    if not isinstance(transition_data, dict):
        return None

    ui_data = transition_data.get("ui")
    preset_key = ui_data.get("transition_style_preset") if isinstance(ui_data, dict) else None
    if preset_key in TRANSITION_STYLE_PRESETS:
        return preset_key

    reader = transition_data.get("reader")
    reader_path = reader.get("path") if isinstance(reader, dict) else None
    if not reader_path:
        return None
    normalized_reader = os.path.normpath(str(reader_path))

    for candidate_key in TRANSITION_STYLE_ORDER:
        mask_path = get_transition_style_mask_path(candidate_key)
        if mask_path and normalized_reader == os.path.normpath(mask_path):
            return candidate_key
    return None


def normalize_transition_style_amount_key(amount_key):
    normalized = str(amount_key or TRANSITION_STYLE_AMOUNT_DEFAULT_KEY)
    if normalized not in TRANSITION_STYLE_AMOUNT_PRESETS:
        return TRANSITION_STYLE_AMOUNT_DEFAULT_KEY
    return normalized


def get_transition_style_amount_key(transition_data):
    """Infer the current transition amount from saved UI metadata."""
    if not isinstance(transition_data, dict):
        return None

    preset_key = get_transition_style_preset_key(transition_data)
    if not preset_key:
        return None

    ui_data = transition_data.get("ui")
    amount_key = ui_data.get(TRANSITION_STYLE_AMOUNT_UI_KEY) if isinstance(ui_data, dict) else None
    return normalize_transition_style_amount_key(amount_key)


def scale_transition_style_contrast(base_contrast, amount_key):
    """Scale a transition preset contrast value without changing timing."""
    amount_key = normalize_transition_style_amount_key(amount_key)
    multiplier = float(TRANSITION_STYLE_AMOUNT_PRESETS[amount_key].get("multiplier", 1.0))
    return 1.0 + ((float(base_contrast) - 1.0) * multiplier)


def resolve_transition_style_target(selection, clip_lookup=None, transition_lookup=None, tr=None):
    """Resolve the active preset target from the current dock selection."""
    tr = tr or (lambda text: text)
    clip_lookup = clip_lookup or (lambda clip_id: Clip.get(id=clip_id))
    transition_lookup = transition_lookup or (lambda transition_id: Transition.get(id=transition_id))

    selection = [sel for sel in (selection or []) if isinstance(sel, dict)]
    clip_ids = [sel.get("id") for sel in selection if sel.get("type") == "clip" and sel.get("id")]
    transition_ids = [
        sel.get("id") for sel in selection if sel.get("type") == "transition" and sel.get("id")
    ]

    default_message = tr("Select one transition, or two overlapping clips on the same track.")

    if len(transition_ids) > 1:
        return {"enabled": False, "mode": None, "message": tr("Select one transition at a time.")}

    if len(transition_ids) == 1:
        transition_item = transition_lookup(transition_ids[0])
        transition_data = _item_data(transition_item)
        if not transition_data:
            return {"enabled": False, "mode": None, "message": default_message}

        position_s, _right_edge, duration_s = timeline_item_span(transition_data)
        if duration_s <= 0.0:
            return {"enabled": False, "mode": None, "message": default_message}

        preset_key = get_transition_style_preset_key(transition_data)
        amount_key = get_transition_style_amount_key(transition_data)
        preset_label = TRANSITION_STYLE_PRESETS.get(preset_key, {}).get("label") if preset_key else None
        summary = tr("Selected transition")
        if preset_label:
            summary = f"{summary} - {preset_label}"

        return {
            "enabled": True,
            "mode": "transition",
            "message": tr("Pick a preset to restyle the selected transition."),
            "summary": summary,
            "transition_id": transition_ids[0],
            "layer": int(_safe_float(transition_data.get("layer", 0))),
            "position": position_s,
            "duration": duration_s,
            "center": position_s + (duration_s / 2.0),
            "current_preset_key": preset_key,
            "current_amount_key": amount_key,
        }

    if len(clip_ids) != 2:
        return {"enabled": False, "mode": None, "message": default_message}

    clip_a = clip_lookup(clip_ids[0])
    clip_b = clip_lookup(clip_ids[1])
    clip_a_data = _item_data(clip_a)
    clip_b_data = _item_data(clip_b)
    if not clip_a_data or not clip_b_data:
        return {"enabled": False, "mode": None, "message": default_message}

    layer_a = int(_safe_float(clip_a_data.get("layer", 0)))
    layer_b = int(_safe_float(clip_b_data.get("layer", 0)))
    if layer_a != layer_b:
        return {
            "enabled": False,
            "mode": None,
            "message": tr("Choose two overlapping clips on the same track."),
        }

    clip_a_left, clip_a_right, _clip_a_duration = timeline_item_span(clip_a_data)
    clip_b_left, clip_b_right, _clip_b_duration = timeline_item_span(clip_b_data)
    overlap_left = max(clip_a_left, clip_b_left)
    overlap_right = min(clip_a_right, clip_b_right)
    overlap_duration = overlap_right - overlap_left
    if overlap_duration <= 0.0:
        return {
            "enabled": False,
            "mode": None,
            "message": tr("Overlap the two selected clips first, then pick a preset."),
        }

    ordered = [
        (clip_a_left, clip_a_right, clip_ids[0]),
        (clip_b_left, clip_b_right, clip_ids[1]),
    ]
    ordered.sort(key=lambda item: (item[0], item[1], item[2]))

    return {
        "enabled": True,
        "mode": "pair",
        "message": tr("Pick a preset to create or restyle the selected overlap."),
        "summary": tr("Selected overlap - %(duration).3f s") % {"duration": overlap_duration},
        "clip_ids": [ordered[0][2], ordered[1][2]],
        "layer": layer_a,
        "position": overlap_left,
        "duration": overlap_duration,
        "center": overlap_left + (overlap_duration / 2.0),
    }


class TransitionPresetDockPanel(QFrame):
    """Compact one-click transition preset controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        tr = getattr(get_app(), "_tr", lambda text: text)

        self._selection = []
        self._target = None
        self._timing_key = "overlap"
        self._amount_key = TRANSITION_STYLE_AMOUNT_DEFAULT_KEY
        self.setObjectName("transitionPresetDockPanel")
        self.setFrameShape(QFrame.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        header = QLabel(f"<strong>{tr('Transitions')}</strong>", self)
        header.setTextFormat(header.textFormat())
        root.addWidget(header)

        self.summary_label = QLabel(tr("Select one transition, or two overlapping clips."), self)
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.hint_label = QLabel(tr("One click applies a stronger handoff without opening the full browser."), self)
        self.hint_label.setWordWrap(True)
        root.addWidget(self.hint_label)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self._preset_buttons = {}
        for index, preset_key in enumerate(TRANSITION_STYLE_ORDER):
            preset = TRANSITION_STYLE_PRESETS[preset_key]
            button = QPushButton(
                f"{tr(preset['label'])}\n{tr(preset['description'])}",
                self,
            )
            button.setMinimumHeight(56)
            button.clicked.connect(
                lambda _checked=False, key=preset_key: self._apply_preset(key)
            )
            button.setToolTip(tr(preset["description"]))
            grid.addWidget(button, index // 2, index % 2)
            self._preset_buttons[preset_key] = button
        root.addLayout(grid)

        amount_header = QLabel(f"<strong>{tr('Amount')}</strong>", self)
        amount_header.setTextFormat(amount_header.textFormat())
        root.addWidget(amount_header)

        amount_grid = QGridLayout()
        amount_grid.setContentsMargins(0, 0, 0, 0)
        amount_grid.setHorizontalSpacing(6)
        amount_grid.setVerticalSpacing(6)
        self._amount_buttons = {}
        for index, amount_key in enumerate(TRANSITION_STYLE_AMOUNT_ORDER):
            amount = TRANSITION_STYLE_AMOUNT_PRESETS[amount_key]
            button = QPushButton(tr(amount["label"]), self)
            button.setCheckable(True)
            button.setMinimumHeight(30)
            button.clicked.connect(lambda _checked=False, key=amount_key: self._select_amount(key))
            amount_grid.addWidget(button, 0, index)
            self._amount_buttons[amount_key] = button
        root.addLayout(amount_grid)

        timing_header = QLabel(f"<strong>{tr('Timing')}</strong>", self)
        timing_header.setTextFormat(timing_header.textFormat())
        root.addWidget(timing_header)

        bpm_row = QHBoxLayout()
        bpm_row.setContentsMargins(0, 0, 0, 0)
        bpm_row.setSpacing(6)
        bpm_label = QLabel(tr("BPM"), self)
        bpm_row.addWidget(bpm_label)

        self.bpm_spin = QDoubleSpinBox(self)
        self.bpm_spin.setDecimals(1)
        self.bpm_spin.setMinimum(40.0)
        self.bpm_spin.setMaximum(240.0)
        self.bpm_spin.setSingleStep(1.0)
        self.bpm_spin.setValue(120.0)
        self.bpm_spin.valueChanged.connect(self._update_timing_preview)
        bpm_row.addWidget(self.bpm_spin)
        bpm_row.addStretch(1)
        root.addLayout(bpm_row)

        timing_grid = QGridLayout()
        timing_grid.setContentsMargins(0, 0, 0, 0)
        timing_grid.setHorizontalSpacing(6)
        timing_grid.setVerticalSpacing(6)
        self._timing_buttons = {}
        for index, timing_key in enumerate(TRANSITION_TIMING_ORDER):
            timing = TRANSITION_TIMING_PRESETS[timing_key]
            button = QPushButton(tr(timing["label"]), self)
            button.setCheckable(True)
            button.setMinimumHeight(32)
            button.clicked.connect(lambda _checked=False, key=timing_key: self._select_timing(key))
            timing_grid.addWidget(button, index // 3, index % 3)
            self._timing_buttons[timing_key] = button
        root.addLayout(timing_grid)

        self.timing_label = QLabel(
            tr("Beat timing uses nearby markers when possible, then falls back to the BPM field."),
            self,
        )
        self.timing_label.setWordWrap(True)
        root.addWidget(self.timing_label)

        marker_header = QLabel(f"<strong>{tr('Beat Markers')}</strong>", self)
        marker_header.setTextFormat(marker_header.textFormat())
        root.addWidget(marker_header)

        marker_grid = QGridLayout()
        marker_grid.setContentsMargins(0, 0, 0, 0)
        marker_grid.setHorizontalSpacing(6)
        marker_grid.setVerticalSpacing(6)
        self._marker_buttons = {}
        for index, helper_key in enumerate(TRANSITION_MARKER_HELPER_ORDER):
            helper = TRANSITION_MARKER_HELPERS[helper_key]
            button = QPushButton(tr(helper["label"]), self)
            button.setMinimumHeight(32)
            button.clicked.connect(lambda _checked=False, key=helper_key: self._apply_marker_helper(key))
            button.setToolTip(tr(helper["description"]))
            marker_grid.addWidget(button, index // 2, index % 2)
            self._marker_buttons[helper_key] = button
        root.addLayout(marker_grid)

        self.marker_label = QLabel(
            tr("Drop a playhead marker, mark the cut, find a nearby hit, or create a one-beat window."),
            self,
        )
        self.marker_label.setWordWrap(True)
        root.addWidget(self.marker_label)

        window = getattr(get_app(), "window", None)
        if window and getattr(window, "propertyTableView", None):
            window.propertyTableView.loadProperties.connect(self.update_selection)

        self._sync_timing_buttons()
        self._set_controls_enabled(False)
        self.hide()

    def _set_controls_enabled(self, enabled):
        for child in self.findChildren(QWidget):
            if child in (self.summary_label, self.hint_label, self.timing_label):
                continue
            child.setEnabled(enabled)

    def _sync_timing_buttons(self):
        for timing_key, button in self._timing_buttons.items():
            button.setChecked(timing_key == self._timing_key)

    def _sync_amount_buttons(self):
        for amount_key, button in self._amount_buttons.items():
            button.setChecked(amount_key == self._amount_key)

    def _select_amount(self, amount_key):
        self._amount_key = normalize_transition_style_amount_key(amount_key)
        self._sync_amount_buttons()
        if not self._target or not self._target.get("enabled"):
            return
        current_preset_key = self._target.get("current_preset_key")
        if current_preset_key in TRANSITION_STYLE_PRESETS:
            self._apply_preset(current_preset_key)

    def _current_marker_positions(self):
        positions = []
        for marker in Marker.filter():
            marker_data = _item_data(marker)
            if not marker_data:
                continue
            positions.append(marker_data.get("position"))
        return positions

    def _current_playhead_position(self):
        timeline = getattr(get_app().window, "timeline", None)
        if timeline and hasattr(timeline, "current_playhead_position_seconds"):
            try:
                return float(timeline.current_playhead_position_seconds())
            except Exception:
                pass
        preview_thread = getattr(get_app().window, "preview_thread", None)
        fps = get_app().project.get("fps") or {"num": 30, "den": 1}
        fps_float = float(fps.get("num", 30)) / float(fps.get("den", 1))
        if not preview_thread or fps_float <= 0.0:
            return 0.0
        return float(getattr(preview_thread, "current_frame", 1) - 1) / fps_float

    def _current_span_limits(self):
        if not self._target or not self._target.get("enabled"):
            return None
        if self._target.get("mode") == "pair":
            left_edge = _safe_float(self._target.get("position"), 0.0)
            duration_s = _safe_float(self._target.get("duration"), 0.0)
            return {
                "left": left_edge,
                "right": left_edge + max(0.0, duration_s),
            }
        if self._target.get("mode") == "transition":
            transition_id = self._target.get("transition_id")
            if not transition_id:
                return None
            transition_item = Transition.get(id=transition_id)
            transition_data = _item_data(transition_item)
            if not transition_data:
                return None
            clips = Clip.filter(layer=int(_safe_float(transition_data.get("layer", 0))))
            return resolve_transition_overlap_span(transition_data, clips)
        return None

    def _update_timing_preview(self):
        if not self._target or not self._target.get("enabled"):
            self.timing_label.setText(
                get_app()._tr("Beat timing uses nearby markers when possible, then falls back to the BPM field.")
            )
            self.marker_label.setText(
                get_app()._tr("Drop a playhead marker, mark the cut, find a nearby hit, or create a one-beat window.")
            )
            return

        fps = get_app().project.get("fps") or {"num": 30, "den": 1}
        fps_float = float(fps.get("num", 30)) / float(fps.get("den", 1))
        frame_duration = 1.0 / fps_float if fps_float > 0.0 else 0.0
        marker_positions = self._current_marker_positions()
        self.timing_label.setText(
            describe_transition_timing_target(
                self._target,
                self._timing_key,
                marker_positions=marker_positions,
                fallback_bpm=self.bpm_spin.value(),
                frame_duration=frame_duration,
                span_limits=self._current_span_limits(),
                tr=get_app()._tr,
            )
        )
        marker_plan = build_transition_beat_marker_plan(
            self._target,
            "beat_pair",
            playhead_position=self._current_playhead_position(),
            marker_positions=marker_positions,
            fallback_bpm=self.bpm_spin.value(),
        )
        if marker_plan and marker_plan.get("beat_info"):
            beat_info = marker_plan["beat_info"]
            self.marker_label.setText(
                get_app()._tr("Beat Pair - one beat window from %(source)s") % {
                    "source": str(beat_info.get("source_label") or "120 BPM fallback")
                }
            )
        else:
            self.marker_label.setText(
                get_app()._tr("Drop a playhead marker, mark the cut, find a nearby hit, or create a one-beat window.")
            )

    def _select_timing(self, timing_key):
        if timing_key not in TRANSITION_TIMING_PRESETS:
            return
        self._timing_key = timing_key
        self._sync_timing_buttons()
        self._update_timing_preview()

        if not self._target or not self._target.get("enabled"):
            return
        if self._target.get("mode") != "transition":
            return
        timeline = getattr(get_app().window, "timeline", None)
        if not timeline:
            return
        if timeline.Apply_Transition_Beat_Timing(timing_key, self.bpm_spin.value()):
            self.refresh_from_current_selection()

    def refresh_from_current_selection(self):
        window = getattr(get_app(), "window", None)
        selection = list(getattr(window, "selected_items", []) or []) if window else []
        self.update_selection(selection)

    def update_selection(self, selection):
        self._selection = list(selection or [])
        has_relevant_selection = any(
            isinstance(sel, dict) and sel.get("type") in ("clip", "transition")
            for sel in self._selection
        )
        if not has_relevant_selection:
            self._target = None
            self.summary_label.setText(get_app()._tr("Select one transition, or two overlapping clips."))
            self.hint_label.setText(
                get_app()._tr("One click applies a stronger handoff without opening the full browser.")
            )
            self._set_controls_enabled(False)
            self.hide()
            return

        self.show()
        self._target = resolve_transition_style_target(
            self._selection,
            tr=get_app()._tr,
        )
        if self._target.get("current_amount_key") in TRANSITION_STYLE_AMOUNT_PRESETS:
            self._amount_key = self._target["current_amount_key"]
        self.summary_label.setText(
            str(self._target.get("summary") or get_app()._tr("Transition presets"))
        )
        self.hint_label.setText(
            str(self._target.get("message") or get_app()._tr("Pick a preset to apply."))
        )
        self._set_controls_enabled(bool(self._target.get("enabled")))
        self._sync_amount_buttons()
        self._sync_timing_buttons()
        self._update_timing_preview()

    def _apply_preset(self, preset_key):
        if not self._target or not self._target.get("enabled"):
            return
        timeline = getattr(get_app().window, "timeline", None)
        if not timeline:
            return
        if timeline.Apply_Transition_Style_Preset(
            preset_key,
            timing_key=self._timing_key,
            fallback_bpm=self.bpm_spin.value(),
            amount_key=self._amount_key,
        ):
            self.refresh_from_current_selection()

    def _apply_marker_helper(self, helper_key):
        timeline = getattr(get_app().window, "timeline", None)
        if not timeline:
            return
        if timeline.Apply_Transition_Beat_Marker_Helper(
            helper_key,
            fallback_bpm=self.bpm_spin.value(),
        ):
            self.refresh_from_current_selection()
