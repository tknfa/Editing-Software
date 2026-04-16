"""
 @file
 @brief This file contains re-time keyframe logic (for Time->Fast/Slow menu, Timing mode on timeline)
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2025 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import copy
import json
import math
import re
import openshot
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from classes.app import get_app
from classes.query import Clip


_BEZIER_INTERPOLATION = int(getattr(openshot, "BEZIER", 0))
RETIME_EASING_ORDER = ("linear", "hold", "ease_in", "ease_out", "ease_in_out")
RETIME_EASING_PRESETS = {
    "linear": {
        "label": "Linear",
        "interpolation": int(getattr(openshot, "LINEAR", 1)),
        "handles": None,
    },
    "hold": {
        "label": "Hold",
        "interpolation": int(getattr(openshot, "CONSTANT", 2)),
        "handles": None,
    },
    "ease_in": {
        "label": "Ease In",
        "interpolation": _BEZIER_INTERPOLATION,
        "handles": (0.420, 0.000, 1.000, 1.000),
    },
    "ease_out": {
        "label": "Ease Out",
        "interpolation": _BEZIER_INTERPOLATION,
        "handles": (0.000, 0.000, 0.580, 1.000),
    },
    "ease_in_out": {
        "label": "Ease In/Out",
        "interpolation": _BEZIER_INTERPOLATION,
        "handles": (0.420, 0.000, 0.580, 1.000),
    },
}
RETIME_AUDIO_BEHAVIOR_ORDER = ("source_default", "pitch_shift", "mute")
RETIME_AUDIO_BEHAVIORS = {
    "source_default": {
        "label": "Source Default",
        "audio_label": "Source Default",
        "pitch_label": "Pitch shifts",
        "target": -1.0,
    },
    "pitch_shift": {
        "label": "Pitch Shifts With Speed",
        "audio_label": "Enabled",
        "pitch_label": "Pitch shifts",
        "target": 1.0,
    },
    "mute": {
        "label": "Mute Retimed Audio",
        "audio_label": "Muted",
        "pitch_label": "Muted",
        "target": 0.0,
    },
    "none": {
        "label": "No Audio Source",
        "audio_label": "No audio",
        "pitch_label": "N/A",
        "target": None,
    },
}


def _project_fps_float():
    proj_fps = get_app().project.get("fps") or {"num": 30, "den": 1}
    return float(proj_fps.get("num", 30)) / float(proj_fps.get("den", 1))


def _minimum_duration_seconds(pfps):
    """Return the minimum clip span for the given project FPS."""
    if not math.isfinite(pfps) or pfps <= 0.0:
        return 1.0
    return 1.0 / pfps


def get_clip_duration_seconds(clip_data, pfps):
    """Return a frame-snapped clip duration in seconds."""
    minimum = _minimum_duration_seconds(pfps)
    start_s = float(clip_data.get("start", 0.0) or 0.0)
    end_s = float(clip_data.get("end", start_s) or start_s)
    duration_s = end_s - start_s
    if duration_s <= 0.0:
        duration_s = float(clip_data.get("duration", 0.0) or 0.0)
    if duration_s <= 0.0:
        duration_s = minimum
    duration_frames = max(1, int(round(duration_s * pfps)))
    return duration_frames / pfps


def get_clip_time_direction(clip_data):
    """Return the clip's current overall playback direction."""
    time_data = clip_data.get("time")
    points = time_data.get("Points") if isinstance(time_data, dict) else None
    if isinstance(points, list):
        sortable = []
        for point in points:
            co = point.get("co") if isinstance(point, dict) else None
            if not isinstance(co, dict):
                continue
            x_val = co.get("X")
            y_val = co.get("Y")
            if x_val is None or y_val is None:
                continue
            sortable.append((float(x_val), float(y_val)))
        if len(sortable) >= 2:
            sortable.sort(key=lambda entry: entry[0])
            return 1 if sortable[-1][1] >= sortable[0][1] else -1
    return 1


def _sorted_time_coordinates(clip_data):
    """Return the clip time-curve coordinates ordered by project X."""
    time_data = clip_data.get("time")
    points = time_data.get("Points") if isinstance(time_data, dict) else None
    if not isinstance(points, list):
        return []

    sortable = []
    for point in points:
        co = point.get("co") if isinstance(point, dict) else None
        if not isinstance(co, dict):
            continue
        x_val = co.get("X")
        y_val = co.get("Y")
        if x_val is None or y_val is None:
            continue
        sortable.append((float(x_val), float(y_val)))
    sortable.sort(key=lambda entry: entry[0])
    return sortable


def get_clip_average_speed(clip_data, pfps):
    """Return the clip's average playback speed relative to timeline duration."""
    current_duration = get_clip_duration_seconds(clip_data, pfps)
    if current_duration <= 0.0:
        return 1.0

    sortable = _sorted_time_coordinates(clip_data)
    if len(sortable) < 2:
        return 1.0

    source_frames = abs(sortable[-1][1] - sortable[0][1])
    if source_frames <= 0.0:
        return 0.0

    source_duration = source_frames / pfps if pfps > 0.0 else source_frames
    if source_duration <= 0.0:
        return 0.0
    return source_duration / current_duration


def get_clip_retime_summary(clip_data, pfps):
    """Summarize the current retime state of a clip for the dock panel."""
    current_duration = get_clip_duration_seconds(clip_data, pfps)
    direction = get_clip_time_direction(clip_data)
    average_speed = get_clip_average_speed(clip_data, pfps)
    time_points = _sorted_time_coordinates(clip_data)
    point_count = len(time_points)
    has_ramp = point_count > 2

    if point_count <= 1:
        curve_label = "Straight"
    elif has_ramp:
        curve_label = f"Ramp ({point_count} points)"
    else:
        curve_label = "Straight"

    return {
        "duration": current_duration,
        "duration_label": _format_duration_label(current_duration),
        "direction": direction,
        "direction_label": "Reverse" if direction < 0 else "Forward",
        "average_speed": average_speed,
        "average_speed_label": f"{average_speed:.3f}x",
        "curve_points": point_count,
        "curve_label": curve_label,
        "has_ramp": has_ramp,
    }


def calculate_custom_retime_metrics(clip_data, pfps, mode, amount):
    """Calculate the target duration/end for a custom retime request."""
    current_duration = get_clip_duration_seconds(clip_data, pfps)
    start_s = float(clip_data.get("start", 0.0) or 0.0)

    if mode == "speed":
        try:
            speed_multiplier = abs(float(amount))
        except (TypeError, ValueError):
            return None
        if not math.isfinite(speed_multiplier) or speed_multiplier <= 0.0:
            return None
        new_duration = current_duration / speed_multiplier
    elif mode == "duration":
        try:
            new_duration = float(amount)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(new_duration):
            return None
    else:
        return None

    minimum = _minimum_duration_seconds(pfps)
    if new_duration <= 0.0:
        new_duration = minimum

    new_duration_frames = max(1, int(round(new_duration * pfps)))
    snapped_duration = new_duration_frames / pfps
    relative_speed = current_duration / snapped_duration if snapped_duration > 0.0 else 1.0

    return {
        "current_duration": current_duration,
        "new_duration": snapped_duration,
        "new_end": start_s + snapped_duration,
        "relative_speed": relative_speed,
    }


def _format_duration_label(seconds_value):
    return f"{seconds_value:.3f} s"


def get_retime_easing_choices():
    tr = getattr(get_app(), "_tr", lambda text: text)
    return [(key, tr(RETIME_EASING_PRESETS[key]["label"])) for key in RETIME_EASING_ORDER]


def get_retime_audio_behavior_choices():
    tr = getattr(get_app(), "_tr", lambda text: text)
    return [(key, tr(RETIME_AUDIO_BEHAVIORS[key]["label"])) for key in RETIME_AUDIO_BEHAVIOR_ORDER]


def normalize_property_filter_token(value):
    token = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    if not token:
        return ""

    aliases = {
        "time_curve": "time",
        "retime": "time",
        "ramp": "time",
    }
    try:
        tr = getattr(get_app(), "_tr", lambda text: text)
        translated_time = re.sub(r"[^a-z0-9]+", "_", tr("Time").strip().lower()).strip("_")
        if translated_time:
            aliases[translated_time] = "time"
    except Exception:
        pass
    return aliases.get(token, token)


def _time_points_list(clip_data):
    time_data = clip_data.get("time") if isinstance(clip_data, dict) else None
    points = time_data.get("Points") if isinstance(time_data, dict) else None
    return points if isinstance(points, list) else []


def _keyframe_point_value(clip_data, property_name, default_value):
    property_data = clip_data.get(property_name) if isinstance(clip_data, dict) else None
    points = property_data.get("Points") if isinstance(property_data, dict) else None
    if not isinstance(points, list) or not points:
        return default_value

    sortable = []
    for point in points:
        frame_value = _point_frame(point)
        point_value = _point_value(point)
        if frame_value is None or point_value is None:
            continue
        sortable.append((frame_value, point_value))
    if not sortable:
        return default_value
    sortable.sort(key=lambda entry: entry[0])
    return sortable[0][1]


def clip_has_audio_source(clip_data):
    reader = clip_data.get("reader") if isinstance(clip_data, dict) else None
    if not isinstance(reader, dict):
        return False
    has_audio = reader.get("has_audio")
    return True if has_audio is None else bool(has_audio)


def clip_has_video_source(clip_data):
    reader = clip_data.get("reader") if isinstance(clip_data, dict) else None
    if not isinstance(reader, dict):
        return False
    has_video = reader.get("has_video")
    return True if has_video is None else bool(has_video)


def get_clip_retime_audio_behavior_key(clip_data):
    if not clip_has_audio_source(clip_data):
        return "none"

    ui_data = clip_data.get("ui") if isinstance(clip_data, dict) else None
    behavior = ui_data.get("retime_audio_behavior") if isinstance(ui_data, dict) else None
    if behavior in RETIME_AUDIO_BEHAVIORS:
        return behavior

    has_audio_override = int(round(_keyframe_point_value(clip_data, "has_audio", -1.0)))
    if has_audio_override == 0:
        return "mute"
    if has_audio_override == 1:
        return "pitch_shift"
    return "source_default"


def get_clip_retime_audio_summary(clip_data):
    behavior_key = get_clip_retime_audio_behavior_key(clip_data)
    behavior_info = RETIME_AUDIO_BEHAVIORS.get(behavior_key, RETIME_AUDIO_BEHAVIORS["none"])
    return {
        "audio_behavior_key": behavior_key,
        "audio_label": behavior_info["audio_label"],
        "pitch_label": behavior_info["pitch_label"],
        "has_audio_source": clip_has_audio_source(clip_data),
        "has_video_source": clip_has_video_source(clip_data),
    }


def apply_clip_retime_audio_behavior(clip_data, behavior_key):
    if not clip_has_audio_source(clip_data):
        return False

    behavior = RETIME_AUDIO_BEHAVIORS.get(behavior_key)
    if not behavior or behavior_key == "none":
        return False

    before_payload = json.dumps(
        {
            "has_audio": clip_data.get("has_audio"),
            "retime_audio_behavior": (
                clip_data.get("ui", {}).get("retime_audio_behavior")
                if isinstance(clip_data.get("ui"), dict)
                else None
            ),
        },
        sort_keys=True,
    )

    target_value = behavior.get("target")
    if target_value is not None:
        point = openshot.Point(1, float(target_value), openshot.CONSTANT)
        clip_data["has_audio"] = {"Points": [json.loads(point.Json())]}

    ui_data = clip_data.get("ui")
    if not isinstance(ui_data, dict):
        ui_data = {}
        clip_data["ui"] = ui_data
    if behavior_key == "source_default":
        ui_data.pop("retime_audio_behavior", None)
    else:
        ui_data["retime_audio_behavior"] = behavior_key

    after_payload = json.dumps(
        {
            "has_audio": clip_data.get("has_audio"),
            "retime_audio_behavior": (
                clip_data.get("ui", {}).get("retime_audio_behavior")
                if isinstance(clip_data.get("ui"), dict)
                else None
            ),
        },
        sort_keys=True,
    )
    return before_payload != after_payload


def _point_frame(point):
    co = point.get("co") if isinstance(point, dict) else None
    if not isinstance(co, dict):
        return None
    x_val = co.get("X")
    if x_val is None:
        return None
    try:
        return int(round(float(x_val)))
    except (TypeError, ValueError):
        return None


def _point_value(point):
    co = point.get("co") if isinstance(point, dict) else None
    if not isinstance(co, dict):
        return None
    y_val = co.get("Y")
    if y_val is None:
        return None
    try:
        return float(y_val)
    except (TypeError, ValueError):
        return None


def get_time_curve_points(clip_data):
    points = [
        point
        for point in _time_points_list(clip_data)
        if _point_frame(point) is not None and _point_value(point) is not None
    ]
    points.sort(key=lambda point: _point_frame(point) or 0)
    return points


def get_time_curve_frame_domain(clip_data, pfps):
    points = get_time_curve_points(clip_data)
    if len(points) >= 2:
        return _point_frame(points[0]) or 1, _point_frame(points[-1]) or 1

    start_s = float(clip_data.get("start", 0.0) or 0.0)
    start_x = int(round(start_s * pfps)) + 1
    duration_s = get_clip_duration_seconds(clip_data, pfps)
    duration_frames = max(1, int(round(duration_s * pfps)))
    return start_x, start_x + duration_frames


def get_clip_playhead_frame(clip_data, pfps, playhead_position, interior=False):
    start_x, end_x = get_time_curve_frame_domain(clip_data, pfps)
    position_s = float(clip_data.get("position", 0.0) or 0.0)
    try:
        playhead_s = float(playhead_position)
    except (TypeError, ValueError):
        playhead_s = position_s
    local_seconds = playhead_s - position_s
    local_seconds = max(0.0, min(local_seconds, get_clip_duration_seconds(clip_data, pfps)))
    frame_value = start_x + int(round(local_seconds * pfps))

    if interior and (end_x - start_x) > 1:
        start_x += 1
        end_x -= 1

    if frame_value < start_x:
        frame_value = start_x
    if frame_value > end_x:
        frame_value = end_x
    return int(frame_value)


def _default_time_curve_values(clip_data, pfps):
    start_s = float(clip_data.get("start", 0.0) or 0.0)
    end_s = float(clip_data.get("end", start_s) or start_s)
    start_y = int(round(start_s * pfps)) + 1
    end_y = int(round(end_s * pfps))
    if get_clip_time_direction(clip_data) < 0:
        return max(1, end_y), max(1, start_y)
    return max(1, start_y), max(1, end_y)


def ensure_time_curve_points(clip_data, pfps):
    if not isinstance(clip_data.get("time"), dict):
        clip_data["time"] = {}
    time_data = clip_data["time"]
    if not isinstance(time_data.get("Points"), list):
        time_data["Points"] = []

    points = _time_points_list(clip_data)
    points[:] = [
        point
        for point in points
        if _point_frame(point) is not None and _point_value(point) is not None
    ]
    start_x, end_x = get_time_curve_frame_domain(clip_data, pfps)
    if len(points) < 2:
        start_y, end_y = _default_time_curve_values(clip_data, pfps)
        time_data["Points"] = [
            {"co": {"X": int(start_x), "Y": int(start_y)}, "interpolation": int(getattr(openshot, "LINEAR", 1))},
            {"co": {"X": int(end_x), "Y": int(end_y)}, "interpolation": int(getattr(openshot, "LINEAR", 1))},
        ]
        points = time_data["Points"]

    points.sort(key=lambda point: _point_frame(point) or 0)
    _finalize_time_points(points, start_x, end_x)
    return points


def get_time_curve_value_bounds(clip_data, points=None):
    points = points or get_time_curve_points(clip_data)
    values = [_point_value(point) for point in points]
    values = [value for value in values if value is not None]
    if not values:
        return 0.0, 0.0
    return min(values), max(values)


def get_time_curve_graph_points(clip_data, pfps):
    points = get_time_curve_points(clip_data)
    if len(points) < 2:
        return {"points": [], "start_frame": None, "end_frame": None, "min_value": None, "max_value": None}

    start_x, end_x = get_time_curve_frame_domain(clip_data, pfps)
    min_value, max_value = get_time_curve_value_bounds(clip_data, points)
    frame_span = max(1.0, float(end_x - start_x))
    value_span = float(max_value - min_value)
    graph_points = []
    for point in points:
        frame_value = _point_frame(point)
        curve_value = _point_value(point)
        if frame_value is None or curve_value is None:
            continue
        x_ratio = (float(frame_value) - float(start_x)) / frame_span
        x_ratio = max(0.0, min(1.0, x_ratio))
        if value_span <= 1e-6:
            y_ratio = 0.5
        else:
            y_ratio = 1.0 - ((float(curve_value) - float(min_value)) / value_span)
            y_ratio = max(0.0, min(1.0, y_ratio))
        graph_points.append(
            {
                "point": point,
                "point_index": len(graph_points),
                "frame": frame_value,
                "value": curve_value,
                "x_ratio": x_ratio,
                "y_ratio": y_ratio,
                "interpolation": int(point.get("interpolation", getattr(openshot, "LINEAR", 1))),
                "handle_left": copy.deepcopy(point.get("handle_left")) if isinstance(point.get("handle_left"), dict) else None,
                "handle_right": copy.deepcopy(point.get("handle_right")) if isinstance(point.get("handle_right"), dict) else None,
                "min_value": min_value,
                "max_value": max_value,
            }
        )
    point_count = len(graph_points)
    for point_info in graph_points:
        point_info["point_count"] = point_count

    return {
        "points": graph_points,
        "start_frame": start_x,
        "end_frame": end_x,
        "min_value": min_value,
        "max_value": max_value,
    }


def _time_curve_segment_easing_label(previous, current):
    linear_mode = int(getattr(openshot, "LINEAR", 1))
    constant_mode = int(getattr(openshot, "CONSTANT", 2))
    bezier_mode = int(getattr(openshot, "BEZIER", 0))
    interpolation = int(current.get("interpolation", linear_mode))
    if interpolation == constant_mode:
        return "Hold"
    if interpolation == linear_mode:
        return "Linear"
    if interpolation != bezier_mode:
        return "Bezier"

    previous_right = previous.get("handle_right") if isinstance(previous.get("handle_right"), dict) else None
    current_left = current.get("handle_left") if isinstance(current.get("handle_left"), dict) else None
    if previous_right and current_left:
        tolerance = 0.04
        for preset_key in ("ease_in", "ease_out", "ease_in_out"):
            handles = RETIME_EASING_PRESETS.get(preset_key, {}).get("handles")
            if not handles:
                continue
            comparisons = (
                abs(float(previous_right.get("X", 0.0)) - float(handles[0])),
                abs(float(previous_right.get("Y", 0.0)) - float(handles[1])),
                abs(float(current_left.get("X", 0.0)) - float(handles[2])),
                abs(float(current_left.get("Y", 0.0)) - float(handles[3])),
            )
            if all(delta <= tolerance for delta in comparisons):
                return RETIME_EASING_PRESETS[preset_key]["label"]
    return "Bezier"


def _time_curve_segment_details(previous, current):
    linear_mode = int(getattr(openshot, "LINEAR", 1))
    constant_mode = int(getattr(openshot, "CONSTANT", 2))
    start_frame = int(previous.get("frame", 0) or 0)
    end_frame = int(current.get("frame", start_frame) or start_frame)
    delta_frames = max(1.0, float(end_frame - start_frame))
    start_value = float(previous.get("value", 0.0) or 0.0)
    end_value = float(current.get("value", start_value) or start_value)
    delta_value = end_value - start_value
    interpolation = int(current.get("interpolation", linear_mode))
    speed = abs(delta_value) / delta_frames if delta_frames > 0.0 else 0.0

    kind = "forward"
    label = "Forward"
    short_label = "FWD"
    if interpolation == constant_mode:
        kind = "hold"
        label = "Hold"
        short_label = "HOLD"
    elif abs(delta_value) <= 0.5:
        kind = "freeze"
        label = "Freeze"
        short_label = "FREEZE"
    elif delta_value < 0.0:
        kind = "reverse"
        label = "Reverse"
        short_label = "REV"

    if kind in ("freeze", "hold"):
        summary_label = label
    else:
        summary_label = f"{label} / {speed:.2f}x"

    return {
        "kind": kind,
        "label": label,
        "short_label": short_label,
        "summary_label": summary_label,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "start_value": start_value,
        "end_value": end_value,
        "speed": speed,
        "speed_label": f"{speed:.2f}x",
        "interpolation": interpolation,
        "easing_label": _time_curve_segment_easing_label(previous, current),
    }


def get_time_curve_preview_segments(clip_data, pfps):
    graph = get_time_curve_graph_points(clip_data, pfps)
    points = graph.get("points") if isinstance(graph, dict) else None
    if not isinstance(points, list) or len(points) < 2:
        return []

    segments = []

    for index in range(1, len(points)):
        previous = points[index - 1]
        current = points[index]
        start_ratio = float(previous.get("x_ratio", 0.0))
        end_ratio = float(current.get("x_ratio", start_ratio))
        if end_ratio < start_ratio:
            start_ratio, end_ratio = end_ratio, start_ratio
        if (end_ratio - start_ratio) <= 1e-6:
            continue

        segment = _time_curve_segment_details(previous, current)
        kind = segment.get("kind")
        if not kind:
            continue
        if kind not in ("freeze", "hold", "reverse"):
            continue

        segment.update(
            {
            "start_ratio": max(0.0, min(1.0, start_ratio)),
            "end_ratio": max(0.0, min(1.0, end_ratio)),
            }
        )

        if segments and segments[-1]["kind"] == segment["kind"]:
            previous_segment = segments[-1]
            if abs(previous_segment["end_ratio"] - segment["start_ratio"]) <= 1e-6:
                previous_segment["end_ratio"] = segment["end_ratio"]
                previous_segment["end_frame"] = segment["end_frame"]
                previous_segment["end_value"] = segment["end_value"]
                previous_segment["speed"] = max(previous_segment["speed"], segment["speed"])
                continue

        segments.append(segment)

    return segments


def get_time_curve_playhead_summary(clip_data, pfps, playhead_position):
    graph = get_time_curve_graph_points(clip_data, pfps)
    points = graph.get("points") if isinstance(graph, dict) else None
    fallback_points = False
    if not isinstance(points, list) or len(points) < 2:
        fallback_points = True
        start_frame, end_frame = get_time_curve_frame_domain(clip_data, pfps)
        start_value, end_value = _default_time_curve_values(clip_data, pfps)
        points = [
            {
                "frame": start_frame,
                "value": start_value,
                "interpolation": int(getattr(openshot, "LINEAR", 1)),
                "handle_right": None,
                "handle_left": None,
            },
            {
                "frame": end_frame,
                "value": end_value,
                "interpolation": int(getattr(openshot, "LINEAR", 1)),
                "handle_right": None,
                "handle_left": None,
            },
        ]

    playhead_frame = get_clip_playhead_frame(clip_data, pfps, playhead_position, interior=False)
    segment_previous = points[0]
    segment_current = points[-1]
    for index in range(1, len(points)):
        current = points[index]
        current_frame = int(current.get("frame", playhead_frame) or playhead_frame)
        if playhead_frame <= current_frame:
            segment_previous = points[index - 1]
            segment_current = current
            break

    segment = _time_curve_segment_details(segment_previous, segment_current)
    if fallback_points:
        if segment.get("interpolation") == int(getattr(openshot, "CONSTANT", 2)):
            source_frame = int(round(segment_previous.get("value", 0.0) or 0.0))
        else:
            start_frame = float(segment_previous.get("frame", playhead_frame) or playhead_frame)
            end_frame = float(segment_current.get("frame", playhead_frame) or playhead_frame)
            start_value = float(segment_previous.get("value", 0.0) or 0.0)
            end_value = float(segment_current.get("value", start_value) or start_value)
            if abs(end_frame - start_frame) <= 1e-6:
                source_frame = int(round(end_value))
            else:
                ratio = (float(playhead_frame) - start_frame) / (end_frame - start_frame)
                ratio = max(0.0, min(1.0, ratio))
                source_frame = int(round(start_value + ((end_value - start_value) * ratio)))
    else:
        source_frame = get_time_curve_value_at_frame(clip_data, pfps, playhead_frame)
        if source_frame is None:
            return None
    if pfps > 0.0:
        source_seconds = max(0.0, float(source_frame - 1) / float(pfps))
    else:
        source_seconds = 0.0

    return {
        "playhead_frame": int(playhead_frame),
        "source_frame": int(source_frame),
        "source_label": f"F{int(source_frame)} / {source_seconds:.3f} s",
        "segment_kind": segment.get("kind"),
        "segment_label": segment.get("summary_label"),
        "speed": segment.get("speed"),
        "speed_label": segment.get("speed_label"),
        "easing_label": segment.get("easing_label"),
    }


def get_time_curve_value_at_frame(clip_data, pfps, frame_value):
    points = get_time_curve_points(clip_data)
    if len(points) < 2:
        points = ensure_time_curve_points(clip_data, pfps)
    if len(points) < 2:
        return None

    frame_value = int(round(frame_value))
    first_frame = _point_frame(points[0]) or frame_value
    last_frame = _point_frame(points[-1]) or frame_value
    if frame_value <= first_frame:
        return int(round(_point_value(points[0]) or 0.0))
    if frame_value >= last_frame:
        return int(round(_point_value(points[-1]) or 0.0))

    for index in range(1, len(points)):
        previous = points[index - 1]
        current = points[index]
        previous_frame = _point_frame(previous)
        current_frame = _point_frame(current)
        previous_value = _point_value(previous)
        current_value = _point_value(current)
        if None in (previous_frame, current_frame, previous_value, current_value):
            continue
        if frame_value > current_frame:
            continue

        interpolation = int(current.get("interpolation", getattr(openshot, "LINEAR", 1)))
        if interpolation == int(getattr(openshot, "CONSTANT", 2)):
            return int(round(previous_value))

        if current_frame <= previous_frame:
            return int(round(current_value))

        ratio = float(frame_value - previous_frame) / float(current_frame - previous_frame)
        value = previous_value + ((current_value - previous_value) * ratio)
        return int(round(value))

    return int(round(_point_value(points[-1]) or 0.0))


def upsert_time_point(clip_data, pfps, frame_value, point_value):
    points = ensure_time_curve_points(clip_data, pfps)
    start_x, end_x = get_time_curve_frame_domain(clip_data, pfps)
    frame_value = int(round(frame_value))
    point_value = int(round(point_value))
    frame_value = max(int(start_x), min(int(end_x), frame_value))

    for point in points:
        if _point_frame(point) == frame_value:
            co = point.setdefault("co", {})
            changed = int(round(float(co.get("Y", 0.0) or 0.0))) != point_value
            co["Y"] = point_value
            return changed, point

    new_point = {
        "co": {"X": frame_value, "Y": point_value},
        "interpolation": int(getattr(openshot, "LINEAR", 1)),
    }
    points.append(new_point)
    points.sort(key=lambda point: _point_frame(point) or 0)
    _finalize_time_points(points, start_x, end_x)
    return True, new_point


def remove_time_point(clip_data, pfps, frame_value, tolerance_frames=1):
    points = ensure_time_curve_points(clip_data, pfps)
    if len(points) <= 2:
        return False

    start_x, end_x = get_time_curve_frame_domain(clip_data, pfps)
    target_frame = int(round(frame_value))
    candidate = None
    candidate_delta = None
    for point in points[1:-1]:
        point_frame = _point_frame(point)
        if point_frame is None:
            continue
        delta = abs(point_frame - target_frame)
        if delta > int(tolerance_frames):
            continue
        if candidate is None or delta < candidate_delta:
            candidate = point
            candidate_delta = delta

    if candidate is None:
        return False

    points.remove(candidate)
    _finalize_time_points(points, start_x, end_x)
    return True


def apply_time_segment_easing(clip_data, pfps, frame_value, preset_key):
    points = ensure_time_curve_points(clip_data, pfps)
    if len(points) < 2:
        return False

    preset = RETIME_EASING_PRESETS.get(preset_key)
    if not preset:
        return False

    frame_value = int(round(frame_value))
    points.sort(key=lambda point: _point_frame(point) or 0)
    target_index = None
    for index in range(1, len(points)):
        point_frame = _point_frame(points[index])
        if point_frame is not None and frame_value <= point_frame:
            target_index = index
            break
    if target_index is None:
        target_index = len(points) - 1

    if target_index <= 0:
        return False

    previous = points[target_index - 1]
    current = points[target_index]
    interpolation = int(preset["interpolation"])
    handles = preset.get("handles")
    changed = int(current.get("interpolation", getattr(openshot, "LINEAR", 1))) != interpolation
    current["interpolation"] = interpolation

    if interpolation == _BEZIER_INTERPOLATION and handles:
        previous_right = previous.get("handle_right") if isinstance(previous.get("handle_right"), dict) else {}
        current_left = current.get("handle_left") if isinstance(current.get("handle_left"), dict) else {}
        new_previous = {"X": float(handles[0]), "Y": float(handles[1])}
        new_current = {"X": float(handles[2]), "Y": float(handles[3])}
        if previous_right != new_previous:
            previous["handle_right"] = new_previous
            changed = True
        if current_left != new_current:
            current["handle_left"] = new_current
            changed = True
    else:
        if "handle_right" in previous:
            previous.pop("handle_right", None)
            changed = True
        if "handle_left" in current:
            current.pop("handle_left", None)
            changed = True

    return changed


class CustomRetimeDialog(QDialog):
    """Collect custom retime settings for one or more clips."""

    def __init__(self, clip_data, fps_float, selection_count=1, parent=None):
        super().__init__(parent)
        tr = getattr(get_app(), "_tr", lambda text: text)

        self.clip_data = clip_data or {}
        self.fps_float = fps_float
        self.current_direction = get_clip_time_direction(self.clip_data)
        current_metrics = calculate_custom_retime_metrics(self.clip_data, self.fps_float, "speed", 1.0) or {
            "current_duration": get_clip_duration_seconds(self.clip_data, self.fps_float),
            "new_duration": get_clip_duration_seconds(self.clip_data, self.fps_float),
            "relative_speed": 1.0,
        }

        self.setWindowTitle(tr("Custom Retime"))
        layout = QFormLayout(self)

        if selection_count > 1:
            layout.addRow(tr("Selected clips"), QLabel(str(selection_count), self))

        self.current_duration_label = QLabel(_format_duration_label(current_metrics["current_duration"]), self)
        layout.addRow(tr("Current duration"), self.current_duration_label)

        self.direction_combo = QComboBox(self)
        self.direction_combo.addItem(tr("Forward"), 1)
        self.direction_combo.addItem(tr("Reverse"), -1)
        self.direction_combo.setCurrentIndex(0 if self.current_direction >= 0 else 1)
        layout.addRow(tr("Direction"), self.direction_combo)

        self.mode_combo = QComboBox(self)
        self.mode_combo.addItem(tr("Relative speed"), "speed")
        self.mode_combo.addItem(tr("Target duration"), "duration")
        layout.addRow(tr("Retime by"), self.mode_combo)

        self.speed_spin = QDoubleSpinBox(self)
        self.speed_spin.setRange(0.01, 1000.0)
        self.speed_spin.setDecimals(3)
        self.speed_spin.setSingleStep(0.05)
        self.speed_spin.setValue(1.0)
        layout.addRow(tr("Speed multiplier"), self.speed_spin)

        self.duration_spin = QDoubleSpinBox(self)
        self.duration_spin.setRange(_minimum_duration_seconds(self.fps_float), 86400.0)
        self.duration_spin.setDecimals(3)
        self.duration_spin.setSingleStep(_minimum_duration_seconds(self.fps_float))
        self.duration_spin.setValue(current_metrics["current_duration"])
        layout.addRow(tr("Target duration"), self.duration_spin)

        self.result_duration_label = QLabel(self)
        layout.addRow(tr("Result duration"), self.result_duration_label)

        self.result_speed_label = QLabel(self)
        layout.addRow(tr("Relative speed"), self.result_speed_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.mode_combo.currentIndexChanged.connect(self._update_preview)
        self.speed_spin.valueChanged.connect(self._update_preview)
        self.duration_spin.valueChanged.connect(self._update_preview)
        self._update_preview()

    def _update_preview(self):
        mode = self.mode_combo.currentData()
        amount = self.speed_spin.value() if mode == "speed" else self.duration_spin.value()
        metrics = calculate_custom_retime_metrics(self.clip_data, self.fps_float, mode, amount)
        speed_enabled = mode == "speed"
        self.speed_spin.setEnabled(speed_enabled)
        self.duration_spin.setEnabled(not speed_enabled)

        if not metrics:
            self.result_duration_label.setText("—")
            self.result_speed_label.setText("—")
            return

        self.result_duration_label.setText(_format_duration_label(metrics["new_duration"]))
        self.result_speed_label.setText(f"{metrics['relative_speed']:.3f}x")

    def get_values(self):
        return {
            "mode": self.mode_combo.currentData(),
            "direction": int(self.direction_combo.currentData()),
            "speed_multiplier": float(self.speed_spin.value()),
            "target_duration": float(self.duration_spin.value()),
        }


class RetimeDockPanel(QFrame):
    """Compact retime controls embedded in the properties dock."""

    QUICK_SPEEDS = (0.5, 1.0, 2.0, 4.0)

    def __init__(self, parent=None):
        super().__init__(parent)
        tr = getattr(get_app(), "_tr", lambda text: text)

        self._selection = []
        self._clip_ids = []
        self._current_playhead_frame = None
        self.setObjectName("retimeDockPanel")
        self.setFrameShape(QFrame.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        header = QLabel(f"<strong>{tr('Retime')}</strong>", self)
        header.setTextFormat(header.textFormat())
        root.addWidget(header)

        self.selection_label = QLabel(tr("Select a clip to edit retime."), self)
        self.selection_label.setWordWrap(True)
        root.addWidget(self.selection_label)

        stats_layout = QGridLayout()
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setHorizontalSpacing(10)
        stats_layout.setVerticalSpacing(4)

        self.duration_value = QLabel("—", self)
        self.direction_value = QLabel("—", self)
        self.speed_value = QLabel("—", self)
        self.curve_value = QLabel("—", self)
        self.audio_value = QLabel("—", self)
        self.pitch_value = QLabel("—", self)

        stats_layout.addWidget(QLabel(tr("Duration"), self), 0, 0)
        stats_layout.addWidget(self.duration_value, 0, 1)
        stats_layout.addWidget(QLabel(tr("Direction"), self), 1, 0)
        stats_layout.addWidget(self.direction_value, 1, 1)
        stats_layout.addWidget(QLabel(tr("Avg speed"), self), 2, 0)
        stats_layout.addWidget(self.speed_value, 2, 1)
        stats_layout.addWidget(QLabel(tr("Curve"), self), 3, 0)
        stats_layout.addWidget(self.curve_value, 3, 1)
        stats_layout.addWidget(QLabel(tr("Audio"), self), 4, 0)
        stats_layout.addWidget(self.audio_value, 4, 1)
        stats_layout.addWidget(QLabel(tr("Pitch"), self), 5, 0)
        stats_layout.addWidget(self.pitch_value, 5, 1)
        root.addLayout(stats_layout)

        playhead_header = QLabel(f"<strong>{tr('At Playhead')}</strong>", self)
        playhead_header.setTextFormat(playhead_header.textFormat())
        root.addWidget(playhead_header)

        playhead_layout = QGridLayout()
        playhead_layout.setContentsMargins(0, 0, 0, 0)
        playhead_layout.setHorizontalSpacing(10)
        playhead_layout.setVerticalSpacing(4)
        self.playhead_source_value = QLabel("—", self)
        self.playhead_segment_value = QLabel("—", self)
        self.playhead_easing_value = QLabel("—", self)
        playhead_layout.addWidget(QLabel(tr("Source"), self), 0, 0)
        playhead_layout.addWidget(self.playhead_source_value, 0, 1)
        playhead_layout.addWidget(QLabel(tr("Segment"), self), 1, 0)
        playhead_layout.addWidget(self.playhead_segment_value, 1, 1)
        playhead_layout.addWidget(QLabel(tr("Easing"), self), 2, 0)
        playhead_layout.addWidget(self.playhead_easing_value, 2, 1)
        root.addLayout(playhead_layout)

        self.playhead_hint_label = QLabel(tr("Select one clip to see playhead detail."), self)
        self.playhead_hint_label.setWordWrap(True)
        root.addWidget(self.playhead_hint_label)

        presets = QHBoxLayout()
        presets.setContentsMargins(0, 0, 0, 0)
        presets.setSpacing(4)
        for speed in self.QUICK_SPEEDS:
            label = f"{speed:g}x"
            button = QPushButton(label, self)
            button.clicked.connect(lambda _checked=False, speed_multiplier=speed: self._apply_speed(speed_multiplier))
            presets.addWidget(button)
        root.addLayout(presets)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(4)
        self.reverse_button = QPushButton(tr("Reverse"), self)
        self.reverse_button.clicked.connect(self._toggle_direction)
        actions.addWidget(self.reverse_button)
        self.custom_button = QPushButton(tr("Custom..."), self)
        self.custom_button.clicked.connect(self._open_custom_dialog)
        actions.addWidget(self.custom_button)
        root.addLayout(actions)

        freeze = QHBoxLayout()
        freeze.setContentsMargins(0, 0, 0, 0)
        freeze.setSpacing(4)
        self.freeze_spin = QDoubleSpinBox(self)
        self.freeze_spin.setRange(_minimum_duration_seconds(_project_fps_float()), 600.0)
        self.freeze_spin.setDecimals(3)
        self.freeze_spin.setSingleStep(0.25)
        self.freeze_spin.setValue(1.0)
        freeze.addWidget(self.freeze_spin)
        self.freeze_button = QPushButton(tr("Freeze"), self)
        self.freeze_button.clicked.connect(self._apply_freeze)
        freeze.addWidget(self.freeze_button)
        self.freeze_zoom_button = QPushButton(tr("Freeze + Zoom"), self)
        self.freeze_zoom_button.clicked.connect(lambda: self._apply_freeze(with_zoom=True))
        freeze.addWidget(self.freeze_zoom_button)
        root.addLayout(freeze)

        ramp = QHBoxLayout()
        ramp.setContentsMargins(0, 0, 0, 0)
        ramp.setSpacing(4)
        self.edit_curve_button = QPushButton(tr("Edit Ramp"), self)
        self.edit_curve_button.clicked.connect(self._focus_time_curve)
        ramp.addWidget(self.edit_curve_button)
        self.add_ramp_button = QPushButton(tr("Add Point"), self)
        self.add_ramp_button.clicked.connect(self._add_ramp_point)
        ramp.addWidget(self.add_ramp_button)
        self.remove_ramp_button = QPushButton(tr("Remove Point"), self)
        self.remove_ramp_button.clicked.connect(self._remove_ramp_point)
        ramp.addWidget(self.remove_ramp_button)
        self.timing_button = QPushButton(self)
        self.timing_button.clicked.connect(self._toggle_timing_tool)
        ramp.addWidget(self.timing_button)
        root.addLayout(ramp)

        easing = QHBoxLayout()
        easing.setContentsMargins(0, 0, 0, 0)
        easing.setSpacing(4)
        self.easing_combo = QComboBox(self)
        for preset_key, label in get_retime_easing_choices():
            self.easing_combo.addItem(label, preset_key)
        default_index = max(0, self.easing_combo.findData("ease_in_out"))
        self.easing_combo.setCurrentIndex(default_index)
        easing.addWidget(self.easing_combo)
        self.apply_easing_button = QPushButton(tr("Apply Easing"), self)
        self.apply_easing_button.clicked.connect(self._apply_segment_easing)
        easing.addWidget(self.apply_easing_button)
        root.addLayout(easing)

        audio = QHBoxLayout()
        audio.setContentsMargins(0, 0, 0, 0)
        audio.setSpacing(4)
        self.audio_behavior_combo = QComboBox(self)
        for behavior_key, label in get_retime_audio_behavior_choices():
            self.audio_behavior_combo.addItem(label, behavior_key)
        default_audio_index = max(0, self.audio_behavior_combo.findData("pitch_shift"))
        self.audio_behavior_combo.setCurrentIndex(default_audio_index)
        audio.addWidget(self.audio_behavior_combo)
        self.apply_audio_behavior_button = QPushButton(tr("Apply Audio"), self)
        self.apply_audio_behavior_button.clicked.connect(self._apply_audio_behavior)
        audio.addWidget(self.apply_audio_behavior_button)
        root.addLayout(audio)

        self.audio_note_label = QLabel(
            tr("Pitch-preserving retime is not wired into the current engine yet. ")
            + tr("Today you can keep pitch-shifted retime audio, use source-default audio, or mute it."),
            self,
        )
        self.audio_note_label.setWordWrap(True)
        root.addWidget(self.audio_note_label)

        window = getattr(get_app(), "window", None)
        if window and getattr(window, "propertyTableView", None):
            window.propertyTableView.loadProperties.connect(self.update_selection)
        if window and getattr(window, "actionTimingTool", None):
            window.actionTimingTool.toggled.connect(self._sync_timing_button)
            self._sync_timing_button(window.actionTimingTool.isChecked())
        preview_thread = getattr(window, "preview_thread", None) if window else None
        preview_worker = getattr(preview_thread, "worker", None) if preview_thread else None
        if preview_worker and hasattr(preview_worker, "position_changed"):
            preview_worker.position_changed.connect(self._handle_preview_frame_changed)

        self._set_controls_enabled(False)
        self.hide()

    def _set_controls_enabled(self, enabled):
        for child in self.findChildren(QWidget):
            if child is self.selection_label:
                continue
            child.setEnabled(enabled)

    def _clip_summaries(self):
        fps_float = _project_fps_float()
        summaries = []
        for clip_id in self._clip_ids:
            clip = Clip.get(id=clip_id)
            if not clip:
                continue
            summary = get_clip_retime_summary(clip.data, fps_float)
            summary.update(get_clip_retime_audio_summary(clip.data))
            summaries.append(summary)
        return summaries

    def _shared_label(self, summaries, key, fallback):
        if not summaries:
            return fallback
        values = {summary.get(key) for summary in summaries}
        if len(values) == 1:
            return next(iter(values))
        return fallback

    def _selected_clip_ids(self):
        return list(self._clip_ids)

    def _clear_playhead_summary(self, hint_text=None):
        self.playhead_source_value.setText("—")
        self.playhead_segment_value.setText("—")
        self.playhead_easing_value.setText("—")
        if hint_text is None:
            hint_text = get_app()._tr("Select one clip to see playhead detail.")
        self.playhead_hint_label.setText(hint_text)

    def _playhead_seconds(self, frame_value=None):
        if frame_value is None:
            frame_value = self._current_playhead_frame
        if frame_value is None:
            preview_thread = getattr(get_app().window, "preview_thread", None)
            frame_value = getattr(preview_thread, "current_frame", None) if preview_thread else None
        if frame_value is None:
            return None
        try:
            frame_value = int(frame_value)
        except (TypeError, ValueError):
            return None
        fps_float = _project_fps_float()
        if fps_float <= 0.0:
            return None
        return max(0.0, float(frame_value - 1) / fps_float)

    def _refresh_playhead_summary(self, frame_value=None):
        playhead_seconds = self._playhead_seconds(frame_value)
        if not self._clip_ids:
            self._clear_playhead_summary(get_app()._tr("Select one clip to see playhead detail."))
            return
        if len(self._clip_ids) != 1:
            self._clear_playhead_summary(get_app()._tr("Playhead detail appears for a single selected clip."))
            return
        if playhead_seconds is None:
            self._clear_playhead_summary(get_app()._tr("Move the playhead to inspect the current retime segment."))
            return

        clip = Clip.get(id=self._clip_ids[0])
        if not clip or not isinstance(getattr(clip, "data", None), dict):
            self._clear_playhead_summary(get_app()._tr("Select one clip to see playhead detail."))
            return

        fps_float = _project_fps_float()
        clip_data = clip.data
        clip_position = float(clip_data.get("position", 0.0) or 0.0)
        clip_duration = get_clip_duration_seconds(clip_data, fps_float)
        if playhead_seconds < clip_position or playhead_seconds > (clip_position + clip_duration):
            self._clear_playhead_summary(get_app()._tr("Move the playhead over the selected clip."))
            return

        summary = get_time_curve_playhead_summary(clip_data, fps_float, playhead_seconds)
        if not summary:
            self._clear_playhead_summary(get_app()._tr("Move the playhead over the selected clip."))
            return

        self.playhead_source_value.setText(str(summary.get("source_label") or "—"))
        self.playhead_segment_value.setText(str(summary.get("segment_label") or "—"))
        self.playhead_easing_value.setText(str(summary.get("easing_label") or "—"))
        self.playhead_hint_label.setText(
            get_app()._tr("Drag points directly on the curve for quick retime shaping.")
        )

    def _handle_preview_frame_changed(self, frame_value):
        self._current_playhead_frame = frame_value
        self._refresh_playhead_summary(frame_value)

    def refresh_from_current_selection(self):
        window = getattr(get_app(), "window", None)
        selection = list(getattr(window, "selected_items", []) or []) if window else []
        self.update_selection(selection)

    def update_selection(self, selection):
        self._selection = list(selection or [])
        self._clip_ids = [
            sel.get("id")
            for sel in self._selection
            if isinstance(sel, dict) and sel.get("type") == "clip" and sel.get("id")
        ]

        summaries = self._clip_summaries()
        if not summaries:
            self.selection_label.setText(get_app()._tr("Select a clip to edit retime."))
            self.duration_value.setText("—")
            self.direction_value.setText("—")
            self.speed_value.setText("—")
            self.curve_value.setText("—")
            self.audio_value.setText("—")
            self.pitch_value.setText("—")
            self._clear_playhead_summary(get_app()._tr("Select one clip to see playhead detail."))
            self._set_controls_enabled(False)
            self.hide()
            return

        self.show()
        self._set_controls_enabled(True)
        clip_count = len(summaries)
        if clip_count == 1:
            self.selection_label.setText(get_app()._tr("Quick retime controls for the selected clip."))
        else:
            self.selection_label.setText(
                get_app()._tr("Applying to %(count)s selected clips.") % {"count": clip_count}
            )

        self.duration_value.setText(self._shared_label(summaries, "duration_label", get_app()._tr("Mixed")))
        self.direction_value.setText(self._shared_label(summaries, "direction_label", get_app()._tr("Mixed")))
        self.speed_value.setText(self._shared_label(summaries, "average_speed_label", get_app()._tr("Mixed")))
        self.curve_value.setText(self._shared_label(summaries, "curve_label", get_app()._tr("Mixed")))
        self.audio_value.setText(self._shared_label(summaries, "audio_label", get_app()._tr("Mixed")))
        self.pitch_value.setText(self._shared_label(summaries, "pitch_label", get_app()._tr("Mixed")))

        shared_audio_behavior = self._shared_label(summaries, "audio_behavior_key", "")
        if shared_audio_behavior and self.audio_behavior_combo.findData(shared_audio_behavior) >= 0:
            self.audio_behavior_combo.blockSignals(True)
            self.audio_behavior_combo.setCurrentIndex(self.audio_behavior_combo.findData(shared_audio_behavior))
            self.audio_behavior_combo.blockSignals(False)

        has_audio_source = any(summary.get("has_audio_source") for summary in summaries)
        self.audio_behavior_combo.setEnabled(has_audio_source)
        self.apply_audio_behavior_button.setEnabled(has_audio_source)
        self.audio_note_label.setEnabled(True)
        self._refresh_playhead_summary()

    def _apply_speed(self, speed_multiplier):
        timeline = getattr(get_app().window, "timeline", None)
        clip_ids = self._selected_clip_ids()
        if not timeline or not clip_ids:
            return
        timeline.apply_relative_speed_preset(clip_ids, speed_multiplier)
        self.refresh_from_current_selection()

    def _toggle_direction(self):
        timeline = getattr(get_app().window, "timeline", None)
        clip_ids = self._selected_clip_ids()
        if not timeline or not clip_ids:
            return
        timeline.toggle_retime_direction(clip_ids)
        self.refresh_from_current_selection()

    def _open_custom_dialog(self):
        timeline = getattr(get_app().window, "timeline", None)
        clip_ids = self._selected_clip_ids()
        if not timeline or not clip_ids:
            return
        timeline.Custom_Retime(clip_ids)
        self.refresh_from_current_selection()

    def _apply_freeze(self, with_zoom=False):
        timeline = getattr(get_app().window, "timeline", None)
        clip_ids = self._selected_clip_ids()
        if not timeline or not clip_ids:
            return
        timeline.apply_freeze_marker(clip_ids, float(self.freeze_spin.value()), zoom=with_zoom)
        self.refresh_from_current_selection()

    def _focus_time_curve(self):
        timeline = getattr(get_app().window, "timeline", None)
        if not timeline:
            return False
        return timeline.Focus_Time_Curve(self._selected_clip_ids())

    def _add_ramp_point(self):
        timeline = getattr(get_app().window, "timeline", None)
        clip_ids = self._selected_clip_ids()
        if not timeline or not clip_ids:
            return
        timeline.Add_Time_Ramp_Point(clip_ids)
        self.refresh_from_current_selection()

    def _remove_ramp_point(self):
        timeline = getattr(get_app().window, "timeline", None)
        clip_ids = self._selected_clip_ids()
        if not timeline or not clip_ids:
            return
        timeline.Remove_Time_Ramp_Point(clip_ids)
        self.refresh_from_current_selection()

    def _apply_segment_easing(self):
        timeline = getattr(get_app().window, "timeline", None)
        clip_ids = self._selected_clip_ids()
        if not timeline or not clip_ids:
            return
        timeline.Apply_Time_Ramp_Easing(clip_ids, self.easing_combo.currentData())
        self.refresh_from_current_selection()

    def _apply_audio_behavior(self):
        timeline = getattr(get_app().window, "timeline", None)
        clip_ids = self._selected_clip_ids()
        if not timeline or not clip_ids:
            return
        timeline.Apply_Retime_Audio_Behavior(clip_ids, self.audio_behavior_combo.currentData())
        self.refresh_from_current_selection()

    def _toggle_timing_tool(self):
        action = getattr(get_app().window, "actionTimingTool", None)
        if action:
            action.trigger()

    def _sync_timing_button(self, enabled):
        tr = getattr(get_app(), "_tr", lambda text: text)
        if enabled:
            self.timing_button.setText(tr("Disable Timing Tool"))
        else:
            self.timing_button.setText(tr("Enable Timing Tool"))


def _calculate_retime_metrics(clip, new_end, pfps):
    start_s = float(clip.data["start"])
    old_end_s = float(clip.data["end"])
    req_end_s = float(new_end)
    new_dur_s = req_end_s - start_s
    if new_dur_s <= 0:
        return None

    # Frame snapping and derived X domain
    new_dur_frames = max(1, int(round(new_dur_s * pfps)))
    new_dur_s = new_dur_frames / pfps
    new_end_s = start_s + new_dur_s

    start_x = int(round(start_s * pfps)) + 1
    old_end_x = int(round(old_end_s * pfps))
    new_end_x = start_x + new_dur_frames

    old_len = max(1, old_end_x - start_x)
    scale = float(new_end_x - start_x) / float(old_len)

    return {
        "start_s": start_s,
        "old_end_s": old_end_s,
        "new_dur_s": new_dur_s,
        "new_end_s": new_end_s,
        "start_x": start_x,
        "new_end_x": new_end_x,
        "scale": scale,
    }


def _iterate_keyframe_lists(clip_dict):
    for value in clip_dict.values():
        if isinstance(value, dict) and isinstance(value.get("Points"), list):
            yield value["Points"]
    objects = clip_dict.get("objects") or {}
    for obj in objects.values():
        if not isinstance(obj, dict):
            continue
        for value in obj.values():
            if isinstance(value, dict) and isinstance(value.get("Points"), list):
                yield value["Points"]
    for eff in clip_dict.get("effects", []) or []:
        if not isinstance(eff, dict):
            continue
        for value in eff.values():
            if isinstance(value, dict) and isinstance(value.get("Points"), list):
                yield value["Points"]


def _scale_points(points, start_x, new_end_x, scale):
    if not isinstance(points, list):
        return
    for point in points:
        co = point.get("co", {})
        x = co.get("X")
        if x is None or x < start_x:
            continue
        nx = start_x + (x - start_x) * scale
        nx = int(round(nx))
        if nx < start_x:
            nx = start_x
        elif nx > new_end_x:
            nx = new_end_x
        co["X"] = nx


def _reverse_time_points(points):
    """Mirror points horizontally (X) across their min/max span and swap handles."""
    if not isinstance(points, list) or not points:
        return

    x_values = [p.get("co", {}).get("X") for p in points if isinstance(p.get("co"), dict) and "X" in p.get("co", {})]
    if not x_values:
        return

    pivot = min(x_values) + max(x_values)

    # Preserve original order to keep segment interpolation mapping intact.
    orig_points = sorted(points, key=lambda p: p.get("co", {}).get("X", 0))

    mirrored = []
    for point in orig_points:
        new_point = copy.deepcopy(point)
        co = new_point.get("co")
        if isinstance(co, dict) and "X" in co:
            co["X"] = pivot - point["co"]["X"]
            hl = new_point.pop("handle_left", None)
            hr = new_point.pop("handle_right", None)
            if hr is not None:
                new_point["handle_left"] = hr
            if hl is not None:
                new_point["handle_right"] = hl
        mirrored.append(new_point)

    # Move per-segment interpolation with its segment. In libopenshot the interpolation
    # lives on the destination point, so when reversing we shift each interpolation one
    # point backward to follow the same segment in the new order.
    for idx in range(len(mirrored) - 1):
        mirrored[idx]["interpolation"] = orig_points[idx + 1].get("interpolation", openshot.LINEAR)
    if mirrored:
        mirrored[-1]["interpolation"] = orig_points[-1].get("interpolation", openshot.LINEAR)

    mirrored.sort(key=lambda p: p.get("co", {}).get("X", 0))
    points[:] = mirrored


def _ensure_time_curve(clip, start_x, new_end_x, old_end_s, pfps, _direction):
    time_data = clip.data.get("time")
    time_points = time_data.get("Points") if isinstance(time_data, dict) else None
    if not isinstance(time_points, list) or len(time_points) < 2:
        y0 = start_x
        y1 = int(round(old_end_s * pfps))
        p0 = openshot.Point(start_x, y0, openshot.LINEAR)
        p1 = openshot.Point(new_end_x, y1, openshot.LINEAR)
        clip.data["time"] = {"Points": [json.loads(p0.Json()), json.loads(p1.Json())]}
        return clip.data["time"]["Points"]

    return time_points


def _finalize_time_points(time_points, start_x, new_end_x):
    if not time_points:
        return
    time_points.sort(key=lambda point: float(point.get("co", {}).get("X", 0)))

    domain_start = int(start_x)
    domain_end = int(new_end_x)
    count = len(time_points)

    # Normalize all X values into the clip domain
    normalized = []
    for point in time_points:
        co = point.setdefault("co", {})
        raw_x = co.get("X", domain_start)
        snapped_x = int(round(raw_x))
        if snapped_x < domain_start:
            snapped_x = domain_start
        elif snapped_x > domain_end:
            snapped_x = domain_end
        normalized.append(snapped_x)

    # Clamp endpoints to the domain bounds
    normalized[0] = domain_start
    normalized[-1] = domain_end

    # Ensure the sequence is non-decreasing from start to end
    for index in range(1, count):
        prev = normalized[index - 1]
        if normalized[index] <= prev:
            normalized[index] = min(domain_end, prev + 1)

    # Make sure there is enough room remaining for trailing points
    for index in range(count - 2, -1, -1):
        remaining = count - index - 1
        max_allowed = domain_end - remaining
        if normalized[index] > max_allowed:
            normalized[index] = max_allowed
        if normalized[index] < domain_start:
            normalized[index] = domain_start
        if index > 0 and normalized[index] <= normalized[index - 1]:
            normalized[index] = min(max_allowed, normalized[index - 1] + 1)

    normalized[0] = domain_start
    normalized[-1] = domain_end

    # Final forward pass to clean up any residual overlap
    for index in range(1, count):
        if normalized[index] <= normalized[index - 1]:
            normalized[index] = min(domain_end, normalized[index - 1] + 1)

    normalized[0] = domain_start
    normalized[-1] = domain_end

    for point, x_val in zip(time_points, normalized):
        point["co"]["X"] = int(x_val)


def retime_clip(clip, new_end, new_position=None, direction=1):
    """Retimes a clip and uniformly rescales ALL keyframes' X (including 'time').
       - X and Y are in PROJECT frames.
       - Mirror the time curve's X for reverse.
    """

    pfps = _project_fps_float()
    metrics = _calculate_retime_metrics(clip, new_end, pfps)
    if not metrics:
        return False

    for points in _iterate_keyframe_lists(clip.data):
        _scale_points(points, metrics["start_x"], metrics["new_end_x"], metrics["scale"])

    time_points = _ensure_time_curve(
        clip,
        metrics["start_x"],
        metrics["new_end_x"],
        metrics["old_end_s"],
        pfps,
        direction,
    )
    if direction == -1:
        _reverse_time_points(time_points)
    _finalize_time_points(time_points, metrics["start_x"], metrics["new_end_x"])

    clip.data["duration"] = float(metrics["new_dur_s"])
    clip.data["end"] = float(metrics["new_end_s"])
    if new_position is not None:
        clip.data["position"] = float(int(round(float(new_position) * pfps)) / pfps)

    return True
