"""
 @file
 @brief Keyframe building, dragging, and selection helpers.
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

import json
import math
import uuid
from PyQt5.QtCore import QPointF, QRectF, QTimer, Qt
from PyQt5.QtGui import QColor
from classes.app import get_app
from classes.clip_utils import clamp_timing_to_media, clip_time_bounds
from classes.logger import log
from classes.query import Clip, Transition, Effect
from classes.query import Marker
from ...retime import get_time_curve_graph_points
from ..colors import effect_color_qcolor


class KeyframeMixin:
    def _keyframe_item_position(self, item):
        """Return the item's timeline position, honoring live preview overrides."""
        if not item:
            return 0.0

        data = item.data if isinstance(getattr(item, "data", None), dict) else {}
        position = data.get("position", 0.0)
        item_id = getattr(item, "id", None)

        overrides = None
        if isinstance(item, Clip):
            overrides = getattr(self, "_pending_clip_overrides", {}).get(item_id)
        elif isinstance(item, Transition):
            overrides = getattr(self, "_pending_transition_overrides", {}).get(item_id)

        if isinstance(overrides, dict) and overrides.get("position") is not None:
            position = overrides.get("position")

        try:
            return float(position or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _lookup_interpolation(self, value):
        try:
            idx = int(value)
        except (TypeError, ValueError):
            idx = 2
        if idx == 0:
            return "bezier"
        if idx == 1:
            return "linear"
        return "constant"

    def _normalize_color(self, value):
        if isinstance(value, QColor):
            col = QColor()
            col.setRgba(value.rgba())
            return col
        if isinstance(value, str):
            col = QColor(value)
            if col.isValid():
                return col
        if isinstance(value, (tuple, list)):
            try:
                r, g, b = value[:3]
                a = value[3] if len(value) > 3 else 255
                col = QColor()
                col.setRgb(int(r), int(g), int(b), int(a))
                return col
            except (TypeError, ValueError):
                return QColor()
        if isinstance(value, (int, float)):
            try:
                col = QColor()
                col.setRgba(int(value))
                return col
            except (TypeError, ValueError):
                return QColor()
        return QColor()

    def _effect_color(self, effect):
        color = self._normalize_color(effect_color_qcolor(effect))
        if not color.isValid():
            color = self._normalize_color(self.keyframe_painter.fill)
        return color

    def _keyframe_rect(self, clip_rect, seconds):
        """Return the timeline-space rectangle for a keyframe icon."""
        size = max(2, self.keyframe_painter.size)
        return self._keyframe_rect_for_marker(clip_rect, seconds, None, size=size)

    def _time_curve_rect(self, clip_rect):
        if not isinstance(clip_rect, QRectF):
            clip_rect = QRectF(clip_rect)
        rect = QRectF(clip_rect)
        if rect.width() <= 0.0 or rect.height() <= 0.0:
            return rect

        pad_x = min(max(6.0, self.keyframe_painter.size * 0.9), max(0.0, rect.width() / 4.0))
        pad_y = min(max(6.0, self.keyframe_painter.size * 0.9), max(0.0, rect.height() / 3.0))
        rect.adjust(pad_x, pad_y, -pad_x, -pad_y)
        if rect.width() <= 1.0 or rect.height() <= 1.0:
            return QRectF(clip_rect)
        return rect

    def _time_curve_y_ratio(self, marker):
        if not isinstance(marker, dict):
            return None
        if not self.isRetimePropertyFilterActive():
            return None
        if marker.get("property_key") != "time":
            return None
        ratio = marker.get("curve_y_ratio")
        if ratio is not None:
            try:
                return max(0.0, min(1.0, float(ratio)))
            except (TypeError, ValueError):
                return None
        curve_value = marker.get("curve_value")
        min_value = marker.get("curve_min")
        max_value = marker.get("curve_max")
        try:
            curve_value = float(curve_value)
            min_value = float(min_value)
            max_value = float(max_value)
        except (TypeError, ValueError):
            return None
        if abs(max_value - min_value) <= 1e-6:
            return 0.5
        ratio = 1.0 - ((curve_value - min_value) / (max_value - min_value))
        return max(0.0, min(1.0, ratio))

    def _retime_marker_lane_center_y(self, clip_rect, size):
        if not isinstance(clip_rect, QRectF):
            clip_rect = QRectF(clip_rect)
        lane_gap = max(10.0, float(size) * 1.2)
        return clip_rect.top() - lane_gap

    def _keyframe_rect_for_marker(self, clip_rect, seconds, marker, size=None):
        size = max(2, size or self.keyframe_painter.size)
        pixels = max(self.pixels_per_second, 0.0001)

        if self._is_retime_curve_marker(marker):
            x = clip_rect.left() + float(seconds or 0.0) * pixels
            y = self._retime_marker_lane_center_y(clip_rect, size)
            return QRectF(x - size / 2.0, y - size / 2.0, size, size)

        curve_ratio = self._time_curve_y_ratio(marker)
        if curve_ratio is not None:
            graph_rect = self._time_curve_rect(clip_rect)
            duration = max(clip_rect.width() / pixels, 1.0 / max(self.fps_float or 1.0, 0.0001))
            x_ratio = max(0.0, min(1.0, float(seconds or 0.0) / duration))
            x = graph_rect.left() + (x_ratio * graph_rect.width())
            y = graph_rect.top() + (curve_ratio * graph_rect.height())
            return QRectF(x - size / 2.0, y - size / 2.0, size, size)

        x = clip_rect.left() + float(seconds or 0.0) * pixels
        baseline = clip_rect.bottom() - 0.5
        top = baseline - size / 2.0
        return QRectF(x - size / 2.0, top, size, size)

    def _is_retime_curve_marker(self, marker):
        if not isinstance(marker, dict):
            return False
        if not getattr(self, "isRetimePropertyFilterActive", lambda: False)():
            return False
        return marker.get("property_key") == "time"

    def _keyframe_hit_rect_for_marker(self, rect, marker):
        if not isinstance(rect, QRectF):
            rect = QRectF(rect)
        padding = 2.0
        if self._is_retime_curve_marker(marker):
            padding = max(6.0, float(self.keyframe_painter.size or 0.0) * 0.7)
        hit_rect = QRectF(rect)
        hit_rect.adjust(-padding, -padding, padding, padding)
        return hit_rect

    def _set_marker_rects(self, marker, rect_timeline, state=None):
        if not isinstance(marker, dict):
            return
        state = state or self.geometry._current_view_state()
        marker["rect_timeline"] = QRectF(rect_timeline)
        marker["rect"] = self._viewport_rect(rect_timeline, state)
        hit_rect_timeline = self._keyframe_hit_rect_for_marker(rect_timeline, marker)
        marker["hit_rect_timeline"] = QRectF(hit_rect_timeline)
        marker["hit_rect"] = self._viewport_rect(hit_rect_timeline, state)

    def _viewport_rect(self, rect, state):
        if not isinstance(rect, QRectF):
            rect = QRectF(rect)
        result = QRectF(rect)
        if state:
            result.translate(-state.get("h_offset", 0.0), -state.get("v_offset", 0.0))
        return result

    def _property_key_from_path(self, path):
        for segment_type, segment_value in reversed(tuple(path or ())):
            if segment_type == "dict" and segment_value not in ("Points", "co", "ui", "cache"):
                return str(segment_value)
        return ""

    def _collect_keyframes_from_data(
        self,
        data,
        *,
        clip_rect,
        clip,
        transition,
        clip_start,
        clip_end,
        owner_id,
        object_type,
        selected,
        color,
        effect=None,
        object_id=None,
        override=None,
        base_path=(),
        view_state=None,
    ):
        if not isinstance(data, (dict, list)):
            return []

        if not isinstance(clip_rect, QRectF):
            clip_rect = QRectF(clip_rect)

        clip_rect_timeline = QRectF(clip_rect)
        view_state = view_state or self.geometry._current_view_state()
        clip_rect_view = self._viewport_rect(clip_rect_timeline, view_state)

        fps = self.fps_float or 1.0
        duration = max(0.0, clip_end - clip_start)
        override = override or {}
        initial_start = float(override.get("initial_start", clip_start) or clip_start)
        initial_end = float(override.get("initial_end", clip_end) or clip_end)
        initial_duration = max(0.0, initial_end - initial_start)
        scale_override = bool(override.get("scale")) and initial_duration > 0 and duration > 0
        show_outside = bool(override.get("show_outside"))
        markers = {}
        time_curve_points = {}
        if clip is not None and object_type == "clip":
            for point_info in get_time_curve_graph_points(data, fps).get("points", []):
                point_obj = point_info.get("point")
                if point_obj is not None:
                    time_curve_points[id(point_obj)] = point_info

        skip_keys = {"effects", "ui", "reader", "cache"}

        def store(frame_value, interpolation_value, point_obj=None, point_path=None, property_key=""):
            if frame_value is None:
                return
            try:
                frame_float = float(frame_value)
            except (TypeError, ValueError):
                return
            seconds_abs = frame_float - 1.0
            seconds_abs /= fps
            dimmed = False
            if scale_override:
                normalized = (seconds_abs - initial_start) / initial_duration
                if normalized < 0.0:
                    normalized = 0.0
                if normalized > 1.0:
                    normalized = 1.0
                local_seconds = normalized * duration
            else:
                local_seconds = seconds_abs - clip_start
                if not show_outside:
                    if local_seconds < -1e-6 or local_seconds > duration + 1e-6:
                        return
                elif local_seconds < -1e-6 or local_seconds > duration + 1e-6:
                    dimmed = True
            frame_int = int(round(frame_float))
            previous = markers.get(frame_int)
            path_value = None
            if point_path is not None:
                try:
                    path_value = tuple(point_path)
                except TypeError:
                    path_value = None

            previous_paths = []
            if previous:
                stored_paths = previous.get("paths")
                if isinstance(stored_paths, (list, tuple)):
                    previous_paths.extend(stored_paths)
                prev_single = previous.get("path")
                if prev_single is not None and prev_single not in previous_paths:
                    previous_paths.append(prev_single)
                if path_value is not None and path_value not in previous_paths:
                    previous_paths.append(path_value)
                if previous_paths:
                    previous["paths"] = tuple(previous_paths)
                    if len(previous_paths) == 1:
                        previous["path"] = previous_paths[0]
                    else:
                        previous["path"] = None
                elif "paths" in previous:
                    previous.pop("paths", None)
                if previous["selected"] and not selected:
                    return
            entry_paths = list(previous_paths)
            if not previous and path_value is not None:
                entry_paths.append(path_value)
            color_value = None
            if isinstance(point_obj, dict):
                for key in ("color", "colour", "icon_color"):
                    val = point_obj.get(key)
                    if val:
                        color_value = val
                        break
                if not color_value:
                    ui_data = point_obj.get("ui") if isinstance(point_obj.get("ui"), dict) else None
                    if ui_data:
                        for key in ("color", "colour", "icon_color"):
                            val = ui_data.get(key)
                            if val:
                                color_value = val
                                break
            entry = {
                "frame": frame_int,
                "seconds": local_seconds,
                "display_seconds": max(0.0, min(local_seconds, duration)) if duration > 0 else 0.0,
                "interpolation": self._lookup_interpolation(interpolation_value),
                "selected": bool(selected),
                "dimmed": dimmed,
                "property_key": property_key,
            }
            if property_key == "time" and point_obj is not None:
                curve_point = time_curve_points.get(id(point_obj))
                if curve_point:
                    entry["curve_y_ratio"] = curve_point.get("y_ratio")
                    entry["curve_value"] = curve_point.get("value")
                    entry["curve_min"] = curve_point.get("min_value")
                    entry["curve_max"] = curve_point.get("max_value")
                    entry["curve_point_index"] = curve_point.get("point_index")
                    entry["curve_point_count"] = curve_point.get("point_count")
            if not color_value and previous:
                color_value = previous.get("color")
            if color_value:
                entry["color"] = color_value
            if entry_paths:
                entry["paths"] = tuple(entry_paths)
                if len(entry_paths) == 1:
                    entry["path"] = entry_paths[0]
            markers[frame_int] = entry

        def walk(obj, path):
            if isinstance(obj, dict):
                points = obj.get("Points")
                if isinstance(points, list) and len(points) > 1:
                    base_path = path + (("dict", "Points"),)
                    property_key = self._property_key_from_path(path)
                    for index, point in enumerate(points):
                        co = point.get("co", {}) if isinstance(point, dict) else {}
                        store(
                            co.get("X"),
                            point.get("interpolation"),
                            point,
                            base_path + (("list", index),),
                            property_key,
                        )
                red = obj.get("red")
                if isinstance(red, dict):
                    red_points = red.get("Points")
                    if isinstance(red_points, list) and len(red_points) > 1:
                        base_path = path + (("dict", "red"), ("dict", "Points"))
                        property_key = self._property_key_from_path(path + (("dict", "red"),))
                        for index, point in enumerate(red_points):
                            co = point.get("co", {}) if isinstance(point, dict) else {}
                            store(
                                co.get("X"),
                                point.get("interpolation"),
                                point,
                                base_path + (("list", index),),
                                property_key,
                            )
                for key, value in obj.items():
                    if key in skip_keys:
                        continue
                    if isinstance(value, (dict, list)):
                        walk(value, path + (("dict", key),))
            elif isinstance(obj, list):
                for index, item in enumerate(obj):
                    if isinstance(item, (dict, list)):
                        walk(item, path + (("list", index),))

        try:
            initial_path = tuple(base_path)
        except TypeError:
            initial_path = ()
        walk(data, initial_path)

        if not markers:
            return []

        object_id = object_id or (
            str(getattr(clip, "id", ""))
            if clip
            else str(getattr(transition, "id", owner_id))
        )
        base_color = self._normalize_color(color)
        if not base_color.isValid():
            base_color = self._normalize_color(self.keyframe_painter.fill)

        result = []
        for frame, info in markers.items():
            rect_timeline = self._keyframe_rect_for_marker(
                clip_rect_timeline, info["seconds"], info
            )
            rect_view = self._viewport_rect(rect_timeline, view_state)
            if object_type == "clip":
                color_obj = self._normalize_color(self.keyframe_painter.fill)
            else:
                color_obj = self._normalize_color(base_color)
                info_color = info.get("color")
                override = self._normalize_color(info_color)
                if override.isValid():
                    color_obj = override
                if not color_obj.isValid():
                    color_obj = self._normalize_color(self.keyframe_painter.fill)
            marker = {
                "type": object_type,
                "owner_id": str(owner_id),
                "clip": clip,
                "transition": transition,
                "effect": effect,
                "frame": info["frame"],
                "display_frame": info["frame"],
                "seconds": info["seconds"],
                "display_seconds": info.get("display_seconds", info["seconds"]),
                "interpolation": info["interpolation"],
                "selected": info["selected"],
                "color": color_obj,
                "clip_rect": QRectF(clip_rect_view),
                "clip_rect_timeline": QRectF(clip_rect_timeline),
                "clip_start": clip_start,
                "clip_end": clip_end,
                "rect": QRectF(rect_view),
                "rect_timeline": QRectF(rect_timeline),
                "object_id": str(object_id),
                "object_type": "clip" if object_type in ("clip", "effect") else "transition",
                "key": (object_type, str(owner_id), info["frame"]),
                "dimmed": info.get("dimmed", False),
                "property_key": info.get("property_key"),
                "curve_y_ratio": info.get("curve_y_ratio"),
                "curve_value": info.get("curve_value"),
                "curve_min": info.get("curve_min"),
                "curve_max": info.get("curve_max"),
                "curve_point_index": info.get("curve_point_index"),
                "curve_point_count": info.get("curve_point_count"),
            }
            if object_type == "effect":
                marker["effect_id"] = str(owner_id)
            paths = info.get("paths")
            if paths:
                try:
                    marker["data_paths"] = tuple(paths)
                except TypeError:
                    pass
                if len(paths) == 1:
                    marker["data_path"] = paths[0]
            else:
                path_value = info.get("path")
                if path_value:
                    marker["data_path"] = path_value
            self._set_marker_rects(marker, rect_timeline, view_state)
            result.append(marker)
        return result

    def _build_clip_keyframes(self, rect, clip, view_state):
        data = clip.data if isinstance(clip.data, dict) else {}
        base_start = float(data.get("start", 0.0) or 0.0)
        base_end = float(data.get("end", base_start) or base_start)
        if base_end < base_start:
            base_end = base_start
        clip_start = base_start
        clip_end = base_end
        override_ctx = None
        overrides = self._pending_clip_overrides.get(clip.id)
        if overrides:
            clip_start = overrides.get("start", clip_start)
            clip_end = overrides.get("end", clip_end)
            if clip_end < clip_start:
                clip_end = clip_start
            initial_start = overrides.get("initial_start", base_start)
            initial_end = overrides.get("initial_end", base_end)
            override_ctx = {
                "initial_start": initial_start,
                "initial_end": initial_end,
                "scale": bool(overrides.get("scale")),
                "show_outside": not bool(overrides.get("scale")),
            }

        clip_selected = clip.id in getattr(self.win, "selected_clips", [])
        effects = data.get("effects", []) if isinstance(data, dict) else []
        selected_effect_ids_global = self._selected_effect_ids()
        effect_selected_ids = set()
        for eff in effects:
            if not isinstance(eff, dict):
                continue
            eff_id = eff.get("id")
            eff_id_str = str(eff_id) if eff_id is not None else ""
            if not eff_id_str:
                continue
            if eff.get("selected") or eff_id_str in selected_effect_ids_global:
                effect_selected_ids.add(eff_id_str)
        if not clip_selected and not effect_selected_ids:
            return []

        markers = []
        base_selected = clip_selected and not bool(effect_selected_ids)
        markers.extend(
            self._collect_keyframes_from_data(
                data,
                clip_rect=rect,
                clip=clip,
                transition=None,
                clip_start=clip_start,
                clip_end=clip_end,
                owner_id=str(clip.id),
                object_type="clip",
                selected=base_selected,
                color=self.keyframe_painter.fill,
                object_id=str(clip.id),
                override=override_ctx,
                view_state=view_state,
            )
        )

        for eff_index, eff in enumerate(effects):
            if not isinstance(eff, dict):
                continue
            effect_id = eff.get("id")
            if effect_id is None:
                continue
            effect_id_str = str(effect_id)
            color = self._effect_color(eff)
            eff_selected = effect_id_str in effect_selected_ids
            markers.extend(
                self._collect_keyframes_from_data(
                    eff,
                    clip_rect=rect,
                    clip=clip,
                    transition=None,
                    clip_start=clip_start,
                    clip_end=clip_end,
                    owner_id=effect_id_str,
                    object_type="effect",
                    selected=eff_selected,
                    color=color,
                    effect=eff,
                    object_id=str(clip.id),
                    override=override_ctx,
                    base_path=(("dict", "effects"), ("list", eff_index)),
                    view_state=view_state,
                )
            )

        return markers

    def _build_transition_keyframes(self, rect, transition, view_state):
        if transition.id not in getattr(self.win, "selected_transitions", []):
            return []
        data = transition.data if isinstance(transition.data, dict) else {}
        base_start = float(data.get("start", 0.0) or 0.0)
        base_end = float(data.get("end", base_start) or base_start)
        clip_start = base_start
        clip_end = base_end
        override_ctx = None
        overrides = self._pending_transition_overrides.get(transition.id)
        if overrides:
            clip_start = overrides.get("start", clip_start)
            clip_end = overrides.get("end", clip_end)
            if clip_end < clip_start:
                clip_end = clip_start
            initial_start = overrides.get("initial_start", base_start)
            initial_end = overrides.get("initial_end", base_end)
            override_ctx = {
                "initial_start": initial_start,
                "initial_end": initial_end,
                "scale": bool(overrides.get("scale")),
                "show_outside": not bool(overrides.get("scale")),
            }
        if clip_end < clip_start:
            clip_end = clip_start
        return self._collect_keyframes_from_data(
            data,
            clip_rect=rect,
            clip=None,
            transition=transition,
            clip_start=clip_start,
            clip_end=clip_end,
            owner_id=str(transition.id),
            object_type="transition",
            selected=True,
            color=self.keyframe_painter.fill,
            object_id=str(transition.id),
            override=override_ctx,
            view_state=view_state,
        )

    def _refresh_keyframe_markers(self):
        self.geometry.ensure()
        state = self.geometry._current_view_state()

        markers = []
        for rect, clip, _selected in self.geometry.iter_clips(viewport=False):
            markers.extend(self._build_clip_keyframes(rect, clip, state))
        for rect, tran, _selected in self.geometry.iter_transitions(viewport=False):
            markers.extend(self._build_transition_keyframes(rect, tran, state))

        if getattr(self, "_property_filter_key", ""):
            markers = [
                marker for marker in markers
                if self.propertyFilterMatches(marker.get("property_key"))
            ]

        drag = self._dragging_keyframe
        if drag and drag.get("key") and markers:
            pending_seconds = drag.get("pending_seconds")
            pending_frame = drag.get("pending_frame")
            for marker in markers:
                if marker.get("key") == drag.get("key"):
                    if pending_seconds is not None:
                        marker["seconds"] = pending_seconds
                        marker["display_seconds"] = pending_seconds
                        clip_timeline = marker.get(
                            "clip_rect_timeline", marker.get("clip_rect")
                        )
                        if isinstance(clip_timeline, QRectF) and not clip_timeline.isNull():
                            rect_timeline = self._keyframe_rect_for_marker(
                                clip_timeline, pending_seconds, marker
                            )
                            pending_y_ratio = drag.get("pending_y_ratio")
                            if pending_y_ratio is not None:
                                marker["curve_y_ratio"] = pending_y_ratio
                            pending_value = drag.get("pending_value")
                            if pending_value is not None:
                                marker["curve_value"] = pending_value
                            self._set_marker_rects(marker, rect_timeline, state)
                            marker["clip_rect"] = self._viewport_rect(
                                clip_timeline, state
                            )
                        else:
                            marker["rect"] = self._keyframe_rect_for_marker(
                                marker.get("clip_rect", QRectF()),
                                pending_seconds,
                                marker,
                            )
                            marker["hit_rect"] = self._keyframe_hit_rect_for_marker(
                                marker["rect"], marker
                            )
                        marker["dimmed"] = False
                    if pending_frame is not None:
                        marker["display_frame"] = pending_frame
                    break

        self._keyframe_markers = markers
        self._keyframes_dirty = False
        self._update_keyframe_marker_viewports(state)

    def _ensure_keyframe_markers(self):
        if getattr(self, "_suspend_keyframe_rebuild", False):
            self._update_keyframe_marker_viewports()
            return
        if self._keyframes_dirty:
            self._refresh_keyframe_markers()
        else:
            self._update_keyframe_marker_viewports()

    def _apply_panel_drag_marker_override(self):
        """Adjust clip-level keyframe marker positions during a panel drag.

        Called from paintEvent AFTER _ensure_keyframe_markers so that
        the override is always the last thing to touch marker rects
        before painting.  This corrects the sub-frame rounding that
        occurs when markers are rebuilt from saved clip data.
        """
        panel_drag = self._dragging_panel_keyframes
        if not panel_drag:
            return
        markers = getattr(self, "_keyframe_markers", None)
        if not markers:
            return
        entries = panel_drag.get("entries") or []
        if not entries:
            return

        base_position = panel_drag.get("base_position", 0.0) or 0.0
        try:
            base_position = float(base_position)
        except (TypeError, ValueError):
            base_position = 0.0
        marker_updates = {}
        pending_by_path = {}
        pending_by_parent_path = {}
        for entry in entries:
            entry_path = self._entry_path_tuple(entry)
            marker = self._find_panel_drag_marker(markers, panel_drag, entry)
            if not marker:
                continue
            pending_seconds = entry.get("pending_seconds")
            if pending_seconds is None:
                continue
            try:
                pending_seconds = float(pending_seconds)
            except (TypeError, ValueError):
                continue
            if entry_path:
                pending_entry = {
                    "seconds": pending_seconds,
                    "frame": entry.get("pending_frame"),
                }
                pending_by_path[entry_path] = pending_entry
                if len(entry_path) > 1:
                    parent_path = entry_path[:-1]
                    pending_by_parent_path.setdefault(parent_path, []).append(pending_entry)
            marker_updates[id(marker)] = {
                "marker": marker,
                "seconds": pending_seconds,
                "frame": entry.get("pending_frame"),
            }

        if not marker_updates and not pending_by_path:
            return

        state = self.geometry._current_view_state()
        def apply_marker_update(marker, update):
            local_seconds = update["seconds"] - base_position
            marker["seconds"] = local_seconds
            marker["display_seconds"] = local_seconds
            pending_frame = update.get("frame")
            if pending_frame is not None:
                marker["display_frame"] = pending_frame
            clip_timeline = marker.get("clip_rect_timeline", marker.get("clip_rect"))
            if isinstance(clip_timeline, QRectF) and not clip_timeline.isNull():
                rect_timeline = self._keyframe_rect_for_marker(
                    clip_timeline, local_seconds, marker
                )
                self._set_marker_rects(marker, rect_timeline, state)
            else:
                marker["rect"] = self._keyframe_rect_for_marker(
                    marker.get("clip_rect", QRectF()), local_seconds, marker
                )
                marker["hit_rect"] = self._keyframe_hit_rect_for_marker(
                    marker["rect"], marker
                )
            marker["dimmed"] = False

        for update in marker_updates.values():
            apply_marker_update(update["marker"], update)

        # If a dragged path still exists on another marker (stale cache/data
        # frame), force it to the same pending drag position this paint cycle.
        # This prevents old pre-snap marker positions from lingering visually.
        if pending_by_path:
            for marker in markers:
                if id(marker) in marker_updates:
                    continue
                if not self._panel_drag_owner_matches_marker(panel_drag, marker):
                    continue
                marker_paths = self._marker_paths_tuples(marker)
                if not marker_paths:
                    continue
                marker_frame = marker.get("frame")
                try:
                    marker_frame = int(marker_frame) if marker_frame is not None else None
                except (TypeError, ValueError):
                    marker_frame = None
                matched_update = None
                for marker_path in marker_paths:
                    matched_update = pending_by_path.get(marker_path)
                    if matched_update:
                        break
                    if len(marker_path) <= 1 or marker_frame is None:
                        continue
                    candidates = pending_by_parent_path.get(marker_path[:-1]) or []
                    if not candidates:
                        continue
                    frame_candidates = []
                    for candidate in candidates:
                        try:
                            candidate_frame = candidate.get("frame")
                            candidate_frame = (
                                int(candidate_frame) if candidate_frame is not None else None
                            )
                        except (TypeError, ValueError):
                            candidate_frame = None
                        if candidate_frame == marker_frame:
                            frame_candidates.append(candidate)
                    if len(frame_candidates) == 1:
                        matched_update = frame_candidates[0]
                        break
                    if len(frame_candidates) > 1:
                        marker_seconds = self._marker_absolute_seconds(marker)
                        if marker_seconds is None:
                            continue
                        best = None
                        best_diff = None
                        for candidate in frame_candidates:
                            try:
                                candidate_seconds = float(candidate.get("seconds"))
                            except (TypeError, ValueError):
                                continue
                            diff = abs(candidate_seconds - marker_seconds)
                            if best_diff is None or diff < best_diff:
                                best_diff = diff
                                best = candidate
                        if best is not None:
                            matched_update = best
                            break
                if matched_update:
                    apply_marker_update(marker, matched_update)

    def _entry_path_tuple(self, entry):
        if not isinstance(entry, dict):
            return None
        path = entry.get("path")
        if not path:
            return None
        try:
            return tuple(path)
        except TypeError:
            return None

    def _marker_paths_tuples(self, marker):
        if not isinstance(marker, dict):
            return []
        marker_paths = marker.get("data_paths")
        if not marker_paths:
            single_path = marker.get("data_path")
            if single_path:
                marker_paths = (single_path,)
        normalized = []
        for marker_path in marker_paths or ():
            try:
                normalized.append(tuple(marker_path))
            except TypeError:
                continue
        return normalized

    def _panel_drag_owner_matches_marker(self, drag, marker):
        if not isinstance(drag, dict) or not isinstance(marker, dict):
            return False
        drag_object_id = drag.get("object_id", "")
        drag_owner_type = drag.get("owner_type", "clip") or "clip"
        drag_clip = drag.get("clip")
        drag_transition = drag.get("transition")
        drag_clip_id = str(getattr(drag_clip, "id", "")) if drag_clip is not None else ""
        drag_transition_id = (
            str(getattr(drag_transition, "id", "")) if drag_transition is not None else ""
        )
        if drag_owner_type == "transition":
            marker_transition = marker.get("transition")
            marker_transition_id = (
                str(getattr(marker_transition, "id", ""))
                if marker_transition is not None
                else ""
            )
            if drag_transition_id and marker_transition_id != drag_transition_id:
                return False
        else:
            marker_clip = marker.get("clip")
            marker_clip_id = (
                str(getattr(marker_clip, "id", "")) if marker_clip is not None else ""
            )
            if drag_clip_id and marker_clip_id != drag_clip_id:
                return False
        if drag_object_id and marker.get("object_id") != drag_object_id:
            return False
        return True

    def _select_marker_by_entry_frames(self, markers, entry):
        if not markers:
            return None
        frame_values = []
        for key in ("pending_frame", "original_frame"):
            value = entry.get(key)
            try:
                if value is not None:
                    frame_values.append(int(value))
            except (TypeError, ValueError):
                continue
        for frame_int in frame_values:
            frame_matches = []
            for marker in markers:
                try:
                    marker_frame = marker.get("frame")
                    if marker_frame is not None and int(marker_frame) == frame_int:
                        frame_matches.append(marker)
                except (TypeError, ValueError):
                    continue
            if len(frame_matches) == 1:
                return frame_matches[0]
            if len(frame_matches) > 1:
                target_seconds = entry.get("pending_seconds", entry.get("original_seconds"))
                try:
                    target_seconds = float(target_seconds)
                except (TypeError, ValueError):
                    target_seconds = None
                if target_seconds is not None:
                    best = None
                    best_diff = None
                    for marker in frame_matches:
                        marker_seconds = self._marker_absolute_seconds(marker)
                        if marker_seconds is None:
                            continue
                        diff = abs(marker_seconds - target_seconds)
                        if best_diff is None or diff < best_diff:
                            best_diff = diff
                            best = marker
                    if best is not None:
                        return best
                return frame_matches[0]
        return None

    def _find_panel_drag_marker(self, markers, drag, entry):
        if not markers or not isinstance(entry, dict):
            return None
        owner_markers = [m for m in markers if self._panel_drag_owner_matches_marker(drag, m)]
        strict_owner = False
        if isinstance(drag, dict):
            strict_owner = bool(
                drag.get("object_id")
                or drag.get("clip") is not None
                or drag.get("transition") is not None
            )
        if strict_owner:
            if not owner_markers:
                return None
            candidates = owner_markers
        else:
            candidates = owner_markers if owner_markers else list(markers)

        entry_path = self._entry_path_tuple(entry)
        if entry_path:
            exact = [m for m in candidates if entry_path in self._marker_paths_tuples(m)]
            if len(exact) == 1:
                return exact[0]
            if len(exact) > 1:
                selected = self._select_marker_by_entry_frames(exact, entry)
                if selected is not None:
                    return selected
                return exact[0]

            if len(entry_path) > 1:
                parent = entry_path[:-1]
                parent_matches = []
                for marker in candidates:
                    for marker_path in self._marker_paths_tuples(marker):
                        if len(marker_path) > 1 and marker_path[:-1] == parent:
                            parent_matches.append(marker)
                            break
                if len(parent_matches) == 1:
                    return parent_matches[0]
                if len(parent_matches) > 1:
                    selected = self._select_marker_by_entry_frames(parent_matches, entry)
                    if selected is not None:
                        return selected

        return self._select_marker_by_entry_frames(candidates, entry)

    def _update_keyframe_marker_viewports(self, state=None):
        markers = getattr(self, "_keyframe_markers", [])
        state = state or self.geometry._current_view_state()
        offsets = (
            state.get("h_offset", 0.0),
            state.get("v_offset", 0.0),
        )
        if offsets == getattr(self, "_keyframe_marker_offsets", (None, None)):
            return

        for marker in markers or []:
            clip_rect_tl = marker.get("clip_rect_timeline")
            if isinstance(clip_rect_tl, QRectF) and not clip_rect_tl.isNull():
                marker["clip_rect"] = self._viewport_rect(clip_rect_tl, state)
            else:
                clip_rect = marker.get("clip_rect")
                if isinstance(clip_rect, QRectF) and not clip_rect.isNull():
                    marker["clip_rect"] = self._viewport_rect(clip_rect, state)

            rect_tl = marker.get("rect_timeline")
            if isinstance(rect_tl, QRectF) and not rect_tl.isNull():
                self._set_marker_rects(marker, rect_tl, state)
            else:
                clip_rect_tl = marker.get("clip_rect_timeline")
                if isinstance(clip_rect_tl, QRectF) and not clip_rect_tl.isNull():
                    rect_tl = self._keyframe_rect_for_marker(
                        clip_rect_tl, marker.get("seconds", 0.0), marker
                    )
                    self._set_marker_rects(marker, rect_tl, state)

        self._keyframe_marker_offsets = offsets

    def _update_snap_keyframe_targets(self, clip):
        if not isinstance(clip, Clip) or self.enable_timing:
            self._snap_keyframe_seconds = []
            return

        clip_id = getattr(clip, "id", None)
        if clip_id is None:
            self._snap_keyframe_seconds = []
            return

        overrides = self._pending_clip_overrides.get(clip.id)
        position = None
        if overrides:
            position = overrides.get("position")
        if position is None:
            position = clip.data.get("position", 0.0)
        try:
            position = float(position)
        except (TypeError, ValueError):
            position = 0.0

        self._ensure_keyframe_markers()
        clip_id_str = str(clip_id)
        seconds = []
        for marker in getattr(self, "_keyframe_markers", []):
            if marker.get("object_id") != clip_id_str:
                continue
            # Use unclamped seconds so trimmed-off keyframes remain snap targets.
            marker_seconds = marker.get("seconds")
            if marker_seconds is None:
                marker_seconds = marker.get("display_seconds")
            if marker_seconds is None:
                continue
            try:
                local_seconds = float(marker_seconds)
            except (TypeError, ValueError):
                continue

            seconds.append(position + local_seconds)

        seconds.sort()
        self._snap_keyframe_seconds = seconds

    def _get_keyframe_at(self, pos):
        self._ensure_keyframe_markers()
        for marker in reversed(self._keyframe_markers):
            rect = marker.get("hit_rect", marker.get("rect"))
            if isinstance(rect, QRectF) and rect.contains(pos):
                return marker
        return None

    def _point_frame_number(self, point, default=None):
        co = point.get("co") if isinstance(point, dict) else None
        if not isinstance(co, dict):
            return default
        try:
            return int(round(float(co.get("X"))))
        except (TypeError, ValueError):
            return default

    def _point_curve_value(self, point, default=None):
        co = point.get("co") if isinstance(point, dict) else None
        if not isinstance(co, dict):
            return default
        try:
            return float(co.get("Y"))
        except (TypeError, ValueError):
            return default

    def _configure_retime_keyframe_drag(self, drag):
        marker = drag.get("marker") if isinstance(drag, dict) else None
        if not self._is_retime_curve_marker(marker):
            return
        clip = marker.get("clip")
        if not clip or not isinstance(getattr(clip, "data", None), dict):
            return
        marker_paths = self._marker_paths_tuples(marker)
        if not marker_paths:
            return
        path = marker_paths[0]
        point = self._resolve_data_path(clip.data, path)
        if not isinstance(point, dict):
            return
        parent_points = self._resolve_data_path(clip.data, path[:-1])
        tail = path[-1] if path else None
        if (
            not isinstance(parent_points, list)
            or not isinstance(tail, tuple)
            or len(tail) != 2
            or tail[0] != "list"
        ):
            return
        try:
            point_index = int(tail[1])
        except (TypeError, ValueError):
            return
        if point_index < 0 or point_index >= len(parent_points):
            return

        current_frame = self._point_frame_number(point, drag.get("current_frame"))
        current_value = self._point_curve_value(point, marker.get("curve_value", 1.0))
        if current_frame is None or current_value is None:
            return

        _max_duration, max_frames = clip_time_bounds(clip.data, clip)
        max_frames = max(int(max_frames or 0), int(round(current_value)), 1)

        frame_min = int(current_frame)
        frame_max = int(current_frame)
        if point_index > 0:
            previous_frame = self._point_frame_number(parent_points[point_index - 1], frame_min - 1)
            frame_min = max(1, int(previous_frame or 0) + 1)
        if point_index < (len(parent_points) - 1):
            next_frame = self._point_frame_number(parent_points[point_index + 1], frame_max + 1)
            frame_max = max(frame_min, int(next_frame or frame_max) - 1)

        drag["current_value"] = float(current_value)
        drag["pending_value"] = float(current_value)
        drag["pending_y_ratio"] = marker.get("curve_y_ratio")
        drag["value_min"] = 1.0
        drag["value_max"] = float(max_frames)
        drag["frame_min"] = frame_min
        drag["frame_max"] = frame_max
        drag["lock_x"] = point_index in (0, len(parent_points) - 1)
        drag["retime_curve"] = True

    def _retime_drag_value_changed(self, drag):
        if not isinstance(drag, dict):
            return False
        try:
            pending_value = drag.get("pending_value")
            current_value = drag.get("current_value")
            if pending_value is None or current_value is None:
                return False
            return int(round(float(pending_value))) != int(round(float(current_value)))
        except (TypeError, ValueError):
            return False

    def _set_keyframe_value_at_path(self, data, path, new_value):
        target = self._resolve_data_path(data, path)
        if not isinstance(target, dict):
            return False
        co = target.get("co")
        if not isinstance(co, dict):
            return False
        co["Y"] = int(round(float(new_value)))
        return True

    def _clamp_keyframe_seconds(self, seconds, clip_start, clip_end):
        max_sec = clip_end
        if self.fps_float:
            max_sec = max(clip_start, clip_end - (1.0 / self.fps_float))
        if seconds < clip_start:
            seconds = clip_start
        if seconds > max_sec:
            seconds = max_sec
        return seconds

    def _move_keyframes_in_object(self, obj, old_frame, new_frame):
        if isinstance(obj, dict):
            points = obj.get("Points")
            if isinstance(points, list):
                for point in points:
                    if not isinstance(point, dict):
                        continue
                    co = point.get("co")
                    if isinstance(co, dict):
                        x_val = co.get("X")
                        try:
                            frame = int(round(float(x_val)))
                        except (TypeError, ValueError):
                            continue
                        if frame == old_frame:
                            co["X"] = new_frame
            for channel in ("red", "green", "blue"):
                chan = obj.get(channel)
                if isinstance(chan, dict):
                    self._move_keyframes_in_object(chan, old_frame, new_frame)
            for key, value in obj.items():
                if key in ("ui",):
                    continue
                if isinstance(value, (dict, list)):
                    self._move_keyframes_in_object(value, old_frame, new_frame)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    self._move_keyframes_in_object(item, old_frame, new_frame)

    def _keyframe_base_position(self, info):
        clip = None
        transition = None
        if isinstance(info, dict):
            clip = info.get("clip")
            transition = info.get("transition")
        else:
            clip = getattr(info, "clip", None)
            transition = getattr(info, "transition", None)

        base_position = 0.0
        if clip:
            base_position = self._keyframe_item_position(clip)
        elif transition:
            base_position = self._keyframe_item_position(transition)
        return base_position

    def _marker_absolute_seconds(self, marker):
        if not isinstance(marker, dict):
            return None
        seconds = marker.get("seconds")
        if seconds is None:
            seconds = marker.get("display_seconds")
        try:
            local = float(seconds)
        except (TypeError, ValueError):
            return None
        base_position = self._keyframe_base_position(marker)
        return base_position + local

    def _compute_keyframe_snap_targets(self, marker):
        if marker is None:
            return []
        self._ensure_keyframe_markers()
        targets = []
        seen = set()

        def add_target(seconds, tolerance=None):
            try:
                value = float(seconds)
            except (TypeError, ValueError):
                return
            if value < 0.0:
                value = 0.0
            key = round(value, 6)
            if key in seen:
                return
            seen.add(key)
            if tolerance is not None:
                try:
                    tol = float(tolerance)
                except (TypeError, ValueError):
                    tol = None
                if tol and tol > 0.0:
                    targets.append({"seconds": value, "tolerance": tol})
                    return
            targets.append(value)

        current_key = marker.get("key")
        for other in getattr(self, "_keyframe_markers", []):
            if other is marker:
                continue
            if current_key is not None and other.get("key") == current_key:
                continue
            absolute = self._marker_absolute_seconds(other)
            if absolute is None:
                continue
            add_target(absolute)

        snap_helper = getattr(self, "snap", None)
        if snap_helper and hasattr(snap_helper, "keyframe_snap_seconds"):
            for entry in snap_helper.keyframe_snap_seconds(include_playhead=False):
                if isinstance(entry, dict):
                    add_target(entry.get("seconds"), entry.get("tolerance"))
                else:
                    add_target(entry)

        clip_obj = marker.get("clip") if isinstance(marker, dict) else None
        if isinstance(clip_obj, Clip):
            clip_data = clip_obj.data if isinstance(clip_obj.data, dict) else {}
            clip_position = self._keyframe_item_position(clip_obj)
            try:
                clip_start = float(clip_data.get("start", 0.0) or 0.0)
            except (TypeError, ValueError):
                clip_start = 0.0
            try:
                clip_end = float(clip_data.get("end", clip_start) or clip_start)
            except (TypeError, ValueError):
                clip_end = clip_start
            if clip_end < clip_start:
                clip_end = clip_start
            duration = clip_end - clip_start
            add_target(clip_position)
            if duration > 0.0:
                add_target(clip_position + duration)

        transition_obj = marker.get("transition") if isinstance(marker, dict) else None
        if isinstance(transition_obj, Transition):
            tran_data = transition_obj.data if isinstance(transition_obj.data, dict) else {}
            tran_position = self._keyframe_item_position(transition_obj)
            try:
                tran_start = float(tran_data.get("start", 0.0) or 0.0)
            except (TypeError, ValueError):
                tran_start = 0.0
            try:
                tran_end = float(tran_data.get("end", tran_start) or tran_start)
            except (TypeError, ValueError):
                tran_end = tran_start
            if tran_end < tran_start:
                tran_end = tran_start
            duration = tran_end - tran_start
            add_target(tran_position)
            if duration > 0.0:
                add_target(tran_position + duration)

        for cached_seconds in getattr(self, "_snap_keyframe_seconds", []) or []:
            add_target(cached_seconds)

        return targets

    def _keyframe_snap_tolerance_seconds(self):
        pps = float(self.pixels_per_second or 0.0)
        if pps <= 0.0:
            return 0.0
        tolerance_px = 0.0
        snap_helper = getattr(self, "snap", None)
        if snap_helper and hasattr(snap_helper, "_snap_tolerance_px"):
            try:
                tolerance_px = float(snap_helper._snap_tolerance_px())
            except (TypeError, ValueError):
                tolerance_px = 0.0
        if tolerance_px <= 0.0:
            return 0.0
        return tolerance_px / pps

    def _snap_absolute_seconds_to_targets(self, absolute_seconds, targets):
        if not self.enable_snapping or not targets:
            return absolute_seconds
        try:
            current = float(absolute_seconds)
        except (TypeError, ValueError):
            return absolute_seconds
        tolerance_sec = self._keyframe_snap_tolerance_seconds()
        if tolerance_sec <= 0.0:
            return absolute_seconds

        best = None
        min_diff = None
        for target in targets:
            tolerance_override = None
            if isinstance(target, dict):
                value = target.get("seconds")
                tolerance_override = target.get("tolerance")
            else:
                value = target
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            local_tol = tolerance_sec
            if tolerance_override is not None:
                try:
                    override = float(tolerance_override)
                except (TypeError, ValueError):
                    override = None
                if override is not None and override > 0.0:
                    local_tol = override

            diff = abs(value - current)
            if diff > local_tol + 1e-9:
                continue
            if min_diff is None or diff < min_diff:
                min_diff = diff
                best = value

        if best is None:
            return absolute_seconds
        return best

    def _apply_keyframe_snapping(self, drag, local_seconds):
        if not drag or not self.enable_snapping:
            return local_seconds
        targets = drag.get("snap_targets")
        if not targets:
            return local_seconds
        try:
            current = float(local_seconds)
        except (TypeError, ValueError):
            return local_seconds
        base_position = self._keyframe_base_position(drag)
        absolute = base_position + current
        snapped_absolute = self._snap_absolute_seconds_to_targets(absolute, targets)
        snapped = snapped_absolute - base_position
        if snapped < 0.0:
            snapped = 0.0
        return snapped

    def _resolve_data_path(self, data, path):
        current = data
        if not path:
            return current
        for entry in path:
            if not isinstance(entry, tuple) or len(entry) != 2:
                return None
            kind, key = entry
            if kind == "dict":
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    return None
            elif kind == "list":
                if not isinstance(current, list):
                    return None
                try:
                    index = int(key)
                except (TypeError, ValueError):
                    return None
                if index < 0 or index >= len(current):
                    return None
                current = current[index]
            else:
                return None
            if current is None:
                return None
        return current

    def _set_keyframe_frame_at_path(self, data, path, new_frame):
        target = self._resolve_data_path(data, path)
        if not isinstance(target, dict):
            return False
        co = target.get("co")
        if not isinstance(co, dict):
            return False
        co["X"] = new_frame
        return True

    def _remove_keyframe_at_path(self, data, path):
        if not path:
            return False
        try:
            path_tuple = tuple(path)
        except TypeError:
            return False
        if not path_tuple:
            return False
        parent_path = path_tuple[:-1]
        last = path_tuple[-1]
        if not isinstance(last, tuple) or len(last) != 2:
            return False
        parent = self._resolve_data_path(data, parent_path)
        kind, key = last
        if kind == "list":
            if not isinstance(parent, list):
                return False
            try:
                index = int(key)
            except (TypeError, ValueError):
                return False
            if index < 0 or index >= len(parent):
                return False
            parent.pop(index)
            return True
        if kind == "dict":
            if not isinstance(parent, dict) or key not in parent:
                return False
            parent.pop(key, None)
            return True
        return False

    def _remove_keyframes_by_paths(self, data, paths):
        if not isinstance(data, (dict, list)):
            return False
        grouped = {}
        for path in paths or ():
            try:
                path_tuple = tuple(path)
            except TypeError:
                continue
            if not path_tuple:
                continue
            parent_path = path_tuple[:-1]
            last = path_tuple[-1]
            if not isinstance(last, tuple) or len(last) != 2:
                continue
            grouped.setdefault(parent_path, []).append(last)
        changed = False
        for parent_path, tails in grouped.items():
            parent = self._resolve_data_path(data, parent_path)
            list_indexes = []
            dict_keys = []
            for tail in tails:
                kind, key = tail
                if kind == "list":
                    try:
                        list_indexes.append(int(key))
                    except (TypeError, ValueError):
                        continue
                elif kind == "dict":
                    dict_keys.append(key)
            if isinstance(parent, list) and list_indexes:
                for index in sorted(set(list_indexes), reverse=True):
                    if 0 <= index < len(parent):
                        parent.pop(index)
                        changed = True
            if isinstance(parent, dict) and dict_keys:
                for key in set(dict_keys):
                    if key in parent:
                        parent.pop(key, None)
                        changed = True
        return changed

    def _remove_keyframes_in_object(self, obj, target_frame):
        changed = False
        if isinstance(obj, dict):
            points = obj.get("Points")
            if isinstance(points, list):
                kept = []
                for point in points:
                    if not isinstance(point, dict):
                        kept.append(point)
                        continue
                    co = point.get("co") if isinstance(point.get("co"), dict) else {}
                    try:
                        frame = int(round(float(co.get("X"))))
                    except (TypeError, ValueError):
                        kept.append(point)
                        continue
                    if frame == target_frame:
                        changed = True
                        continue
                    kept.append(point)
                if changed and len(kept) != len(points):
                    points[:] = kept
            for channel in ("red", "green", "blue"):
                channel_obj = obj.get(channel)
                if isinstance(channel_obj, (dict, list)):
                    if self._remove_keyframes_in_object(channel_obj, target_frame):
                        changed = True
            for key, value in obj.items():
                if key in ("ui", "red", "green", "blue"):
                    continue
                if isinstance(value, (dict, list)):
                    if self._remove_keyframes_in_object(value, target_frame):
                        changed = True
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    if self._remove_keyframes_in_object(item, target_frame):
                        changed = True
        return changed

    def _count_keyframes_by_paths(self, data, paths):
        if not isinstance(data, (dict, list)):
            return 0
        count = 0
        for path in paths or ():
            try:
                path_tuple = tuple(path)
            except TypeError:
                continue
            if not path_tuple:
                continue
            if self._resolve_data_path(data, path_tuple) is not None:
                count += 1
        return count

    def _count_keyframes_in_object(self, obj, target_frame):
        count = 0
        if isinstance(obj, dict):
            points = obj.get("Points")
            if isinstance(points, list):
                for point in points:
                    if not isinstance(point, dict):
                        continue
                    co = point.get("co") if isinstance(point.get("co"), dict) else {}
                    try:
                        frame = int(round(float(co.get("X"))))
                    except (TypeError, ValueError):
                        continue
                    if frame == target_frame:
                        count += 1
            for channel in ("red", "green", "blue"):
                channel_obj = obj.get(channel)
                if isinstance(channel_obj, (dict, list)):
                    count += self._count_keyframes_in_object(channel_obj, target_frame)
            for key, value in obj.items():
                if key in ("ui", "red", "green", "blue"):
                    continue
                if isinstance(value, (dict, list)):
                    count += self._count_keyframes_in_object(value, target_frame)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    count += self._count_keyframes_in_object(item, target_frame)
        return count

    def _keyframe_delete_target_label(self, marker_type, *, clip=None, transition=None, effect_id="", object_id=""):
        marker_type = str(marker_type or "")
        if marker_type == "transition":
            target_id = object_id or str(getattr(transition, "id", "") or "")
            return "transition %s" % target_id if target_id else "transition"
        clip_id = str(getattr(clip, "id", "") or object_id or "")
        if marker_type == "effect":
            effect_label = "effect %s" % effect_id if effect_id else "effect"
            if clip_id:
                return "%s on clip %s" % (effect_label, clip_id)
            return effect_label
        return "clip %s" % clip_id if clip_id else "clip"

    def _panel_selected_keyframe_targets(self):
        targets = {}
        panel_selection = getattr(self, "_panel_selected_keyframes", {}) or {}
        panel_properties = getattr(self, "_panel_properties", {}) or {}
        for track_num, prop_selection in panel_selection.items():
            info = panel_properties.get(track_num)
            if not isinstance(info, dict):
                continue
            track_context = info.get("context")
            for prop in info.get("properties") or []:
                if not isinstance(prop, dict):
                    continue
                prop_key = prop.get("key")
                if not prop_key:
                    continue
                selector = prop_selection.get(prop_key)
                if not selector:
                    continue
                prop_context = self._panel_property_context(prop, track_context)
                for point in prop.get("points") or []:
                    frame_val = point.get("frame")
                    if not self._panel_selection_contains(
                        selector,
                        frame_val,
                        point=point,
                        fallback_context=prop_context,
                    ):
                        continue
                    path = point.get("path")
                    if not path:
                        continue
                    owner = self._panel_resolve_owner(prop, prop_context, point=point)
                    owner_type = owner.get("owner_type") or "clip"
                    object_id = str(owner.get("object_id") or "")
                    clip_obj = owner.get("clip")
                    transition_obj = owner.get("transition")
                    if owner_type == "transition":
                        if not object_id and transition_obj is not None:
                            object_id = str(getattr(transition_obj, "id", "") or "")
                    else:
                        if not object_id and clip_obj is not None:
                            object_id = str(getattr(clip_obj, "id", "") or "")
                    if not object_id:
                        continue
                    key = (owner_type, object_id)
                    target = targets.get(key)
                    if target is None:
                        target = {
                            "owner_type": owner_type,
                            "object_id": object_id,
                            "clip": clip_obj,
                            "transition": transition_obj,
                            "paths": set(),
                        }
                        targets[key] = target
                    try:
                        target["paths"].add(tuple(path))
                    except TypeError:
                        continue
        return list(targets.values())

    def _delete_keyframe_marker_target(self, marker):
        if not isinstance(marker, dict):
            return False
        marker_type = marker.get("type")
        if marker_type not in ("clip", "effect", "transition"):
            return False
        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            return False

        if marker_type == "transition":
            transition = marker.get("transition")
            if not transition:
                transition = Transition.get(id=marker.get("object_id"))
            if not transition or not isinstance(getattr(transition, "data", None), (dict, list)):
                return False
            data_copy = json.loads(json.dumps(transition.data))
            paths = tuple(marker.get("data_paths") or ())
            changed = False
            deleted_count = 0
            if paths:
                deleted_count = self._count_keyframes_by_paths(data_copy, paths)
                changed = self._remove_keyframes_by_paths(data_copy, paths)
                if changed:
                    self._remove_keyframes_by_paths(transition.data, paths)
            if not changed:
                frame_val = marker.get("display_frame", marker.get("frame"))
                try:
                    frame_int = int(frame_val)
                except (TypeError, ValueError):
                    return False
                deleted_count = self._count_keyframes_in_object(data_copy, frame_int)
                changed = self._remove_keyframes_in_object(data_copy, frame_int)
                if changed:
                    self._remove_keyframes_in_object(transition.data, frame_int)
            if not changed:
                return False
            timeline.update_transition_data(
                data_copy,
                only_basic_props=False,
                ignore_refresh=False,
            )
            log.debug(
                "Keyframe delete: removed %d keyframe(s) from %s",
                max(1, deleted_count),
                self._keyframe_delete_target_label(
                    marker_type,
                    transition=transition,
                    object_id=str(marker.get("object_id") or ""),
                ),
            )
            return True

        clip = marker.get("clip")
        if not clip:
            clip = Clip.get(id=marker.get("object_id"))
        if not clip or not isinstance(getattr(clip, "data", None), (dict, list)):
            return False
        data_copy = json.loads(json.dumps(clip.data))
        paths = tuple(marker.get("data_paths") or ())
        changed = False
        deleted_count = 0
        if paths:
            deleted_count = self._count_keyframes_by_paths(data_copy, paths)
            changed = self._remove_keyframes_by_paths(data_copy, paths)
            if changed:
                self._remove_keyframes_by_paths(clip.data, paths)
        if not changed:
            frame_val = marker.get("display_frame", marker.get("frame"))
            try:
                frame_int = int(frame_val)
            except (TypeError, ValueError):
                return False
            if marker_type == "effect":
                effect_id = str(marker.get("owner_id") or marker.get("effect_id") or "")
                effect_copy = None
                effect_live = None
                for eff in data_copy.get("effects", []) if isinstance(data_copy, dict) else []:
                    if str(eff.get("id")) == effect_id:
                        effect_copy = eff
                        break
                for eff in clip.data.get("effects", []) if isinstance(clip.data, dict) else []:
                    if str(eff.get("id")) == effect_id:
                        effect_live = eff
                        break
                if effect_copy is None:
                    return False
                deleted_count = self._count_keyframes_in_object(effect_copy, frame_int)
                changed = self._remove_keyframes_in_object(effect_copy, frame_int)
                if changed and effect_live is not None:
                    self._remove_keyframes_in_object(effect_live, frame_int)
            else:
                deleted_count = self._count_keyframes_in_object(data_copy, frame_int)
                changed = self._remove_keyframes_in_object(data_copy, frame_int)
                if changed:
                    self._remove_keyframes_in_object(clip.data, frame_int)
        if not changed:
            return False
        timeline.update_clip_data(
            data_copy,
            only_basic_props=False,
            ignore_reader=True,
            ignore_refresh=False,
        )
        log.debug(
            "Keyframe delete: removed %d keyframe(s) from %s",
            max(1, deleted_count),
            self._keyframe_delete_target_label(
                marker_type,
                clip=clip,
                effect_id=str(marker.get("owner_id") or marker.get("effect_id") or ""),
                object_id=str(marker.get("object_id") or ""),
            ),
        )
        return True

    def delete_selected_keyframes(self):
        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            return False

        changed = False
        targets = self._panel_selected_keyframe_targets()
        for target in targets:
            owner_type = target.get("owner_type")
            object_id = target.get("object_id")
            if not owner_type or not object_id:
                continue
            paths = tuple(target.get("paths") or ())
            if not paths:
                continue
            if owner_type == "transition":
                transition = target.get("transition") or Transition.get(id=object_id)
                if not transition or not isinstance(getattr(transition, "data", None), (dict, list)):
                    continue
                data_copy = json.loads(json.dumps(transition.data))
                deleted_count = self._count_keyframes_by_paths(data_copy, paths)
                if not self._remove_keyframes_by_paths(data_copy, paths):
                    continue
                self._remove_keyframes_by_paths(transition.data, paths)
                timeline.update_transition_data(
                    data_copy,
                    only_basic_props=False,
                    ignore_refresh=False,
                )
                log.debug(
                    "Keyframe panel delete: removed %d keyframe(s) from %s",
                    max(1, deleted_count),
                    self._keyframe_delete_target_label("transition", transition=transition, object_id=object_id),
                )
                changed = True
                continue

            clip = target.get("clip") or Clip.get(id=object_id)
            if not clip or not isinstance(getattr(clip, "data", None), (dict, list)):
                continue
            data_copy = json.loads(json.dumps(clip.data))
            deleted_count = self._count_keyframes_by_paths(data_copy, paths)
            if not self._remove_keyframes_by_paths(data_copy, paths):
                continue
            self._remove_keyframes_by_paths(clip.data, paths)
            timeline.update_clip_data(
                data_copy,
                only_basic_props=False,
                ignore_reader=True,
                ignore_refresh=False,
            )
            log.debug(
                "Keyframe panel delete: removed %d keyframe(s) from %s",
                max(1, deleted_count),
                self._keyframe_delete_target_label("clip", clip=clip, object_id=object_id),
            )
            changed = True

        if not changed:
            marker = getattr(self, "_active_keyframe_marker", None)
            if not marker:
                marker = getattr(self, "_press_keyframe", None)
            if not marker and isinstance(getattr(self, "_dragging_keyframe", None), dict):
                marker = self._dragging_keyframe.get("marker")
            changed = self._delete_keyframe_marker_target(marker)

        if not changed:
            return False

        self._active_keyframe_marker = None
        self._press_keyframe = None
        self._dragging_keyframe = None
        self._dragging_panel_keyframes = None
        self._clear_panel_selection(None)
        self._snap_keyframe_seconds = []
        self._update_track_panel_properties()
        self.geometry.mark_dirty()
        self._keyframes_dirty = True
        self.update()
        if hasattr(self.win, "show_property_timeout"):
            QTimer.singleShot(0, self.win.show_property_timeout)
        return True

    def _begin_keyframe_transaction(self):
        if not self._dragging_keyframe or self._dragging_keyframe.get("transaction_started"):
            return
        tid = str(uuid.uuid4())
        self._dragging_keyframe["transaction_started"] = True
        self._dragging_keyframe["transaction_id"] = tid
        timeline = getattr(self.win, "timeline", None)
        if timeline:
            timeline.StartKeyframeDrag(
                self._dragging_keyframe.get("object_type", "clip"),
                self._dragging_keyframe.get("object_id", ""),
                tid,
            )

    def _startKeyframeDrag(self):
        if self._press_hit == "panel-keyframe":
            info = self._panel_press_info or {}
            self._start_panel_keyframe_drag(info)
            return
        marker = self._press_keyframe
        self._press_keyframe = None
        if not marker:
            return
        if marker.get("type") == "clip":
            self._panel_select_points_for_clip_marker(marker)
        self.mouse_dragging = True
        self._dragging_keyframe = {
            "marker": marker,
            "key": marker.get("key"),
            "current_frame": marker.get("frame"),
            "pending_frame": marker.get("frame"),
            "pending_seconds": marker.get("display_seconds"),
            "transaction_started": False,
            "object_type": marker.get("object_type", "clip"),
            "object_id": marker.get("object_id", ""),
            "clip": marker.get("clip"),
            "transition": marker.get("transition"),
            "effect_id": marker.get("effect_id"),
            "clip_start": marker.get("clip_start", 0.0),
            "clip_end": marker.get("clip_end", 0.0),
            "moved": False,
            "data_path": marker.get("data_path"),
            "data_paths": tuple(marker.get("data_paths", ()) or ()),
            "clear_existing": bool(getattr(self, "_press_keyframe_clear", True)),
        }
        if not self._dragging_keyframe["data_paths"] and marker.get("data_path"):
            self._dragging_keyframe["data_paths"] = (marker.get("data_path"),)
        self._dragging_keyframe["snap_targets"] = tuple(self._compute_keyframe_snap_targets(marker))
        self._configure_retime_keyframe_drag(self._dragging_keyframe)
        self._fix_cursor(self.cursors.get("resize_x", Qt.SizeHorCursor))
        self._keyframes_dirty = True

    def _move_retime_curve_keyframe(self, drag, event):
        marker = drag.get("marker", {})
        clip_rect = marker.get("clip_rect", QRectF())
        graph_rect = self._time_curve_rect(clip_rect)
        clip_start = float(drag.get("clip_start", 0.0) or 0.0)
        clip_end = float(drag.get("clip_end", clip_start) or clip_start)
        if graph_rect.isNull() or graph_rect.width() <= 1.0 or graph_rect.height() <= 1.0:
            return False
        if clip_end <= clip_start:
            return False

        fps = float(self.fps_float or 0.0)
        duration = max(clip_end - clip_start, 1.0 / max(fps, 1.0))

        current_frame = int(drag.get("current_frame") or marker.get("frame") or 1)
        if drag.get("lock_x"):
            new_frame = current_frame
            if fps > 0.0:
                seconds_abs = (float(new_frame) - 1.0) / fps
                relative_seconds = max(0.0, seconds_abs - clip_start)
            else:
                relative_seconds = float(drag.get("pending_seconds") or marker.get("display_seconds") or 0.0)
        else:
            x_pos = max(graph_rect.left(), min(float(event.pos().x()), graph_rect.right()))
            x_ratio = (x_pos - graph_rect.left()) / max(graph_rect.width(), 1.0)
            x_ratio = max(0.0, min(1.0, x_ratio))
            seconds = clip_start + (x_ratio * duration)
            seconds = self._clamp_keyframe_seconds(seconds, clip_start, clip_end)
            relative_seconds = max(0.0, seconds - clip_start)
            relative_seconds = self._apply_keyframe_snapping(drag, relative_seconds)
            seconds = clip_start + relative_seconds
            seconds = self._clamp_keyframe_seconds(seconds, clip_start, clip_end)
            seconds = self._snap_time(seconds)
            relative_seconds = max(0.0, seconds - clip_start)
            if fps > 0.0:
                new_frame = int(round(seconds * fps)) + 1
            else:
                new_frame = current_frame
            frame_min = drag.get("frame_min")
            frame_max = drag.get("frame_max")
            if frame_min is not None:
                new_frame = max(int(frame_min), new_frame)
            if frame_max is not None:
                new_frame = min(int(frame_max), new_frame)
            if fps > 0.0:
                seconds_abs = (float(new_frame) - 1.0) / fps
                relative_seconds = max(0.0, seconds_abs - clip_start)

        value_min = float(drag.get("value_min", 1.0) or 1.0)
        value_max = float(drag.get("value_max", value_min) or value_min)
        if value_max < value_min:
            value_min, value_max = value_max, value_min
        y_pos = max(graph_rect.top(), min(float(event.pos().y()), graph_rect.bottom()))
        if (value_max - value_min) <= 1e-6:
            y_ratio = 0.5
            new_value = int(round(value_min))
        else:
            y_ratio = (y_pos - graph_rect.top()) / max(graph_rect.height(), 1.0)
            y_ratio = max(0.0, min(1.0, y_ratio))
            new_value = value_min + ((1.0 - y_ratio) * (value_max - value_min))
            new_value = int(round(new_value))
            new_value = max(int(round(value_min)), min(int(round(value_max)), new_value))

        drag["pending_seconds"] = relative_seconds
        drag["pending_frame"] = int(new_frame)
        drag["pending_value"] = float(new_value)
        drag["pending_y_ratio"] = y_ratio
        marker["curve_value"] = float(new_value)
        marker["curve_y_ratio"] = y_ratio
        marker["curve_min"] = value_min
        marker["curve_max"] = value_max

        absolute_seconds = self._keyframe_base_position(marker) + relative_seconds
        self._panel_preview_marker(
            marker,
            drag.get("current_frame"),
            int(new_frame),
            absolute_seconds,
            drag_paths=drag.get("data_paths"),
        )
        if int(new_frame) != int(drag.get("current_frame") or new_frame) or self._retime_drag_value_changed(drag):
            drag["moved"] = True
        self._seek_to_marker_frame(marker, int(new_frame), start_preroll=False)
        self._keyframes_dirty = True
        self.update()
        return True

    def _keyframeMove(self, event):
        if self._dragging_panel_keyframes:
            self._panel_keyframe_move(event)
            return
        drag = self._dragging_keyframe
        if not drag:
            return
        marker = drag.get("marker", {})
        if drag.get("retime_curve"):
            if self._move_retime_curve_keyframe(drag, event):
                return
        clip_rect = marker.get("clip_rect", QRectF())
        clip_start = drag.get("clip_start", 0.0)
        clip_end = drag.get("clip_end", clip_start)
        if clip_rect.isNull() or clip_end <= clip_start or self.pixels_per_second <= 0:
            return

        x = event.pos().x()
        x = max(clip_rect.left(), min(x, clip_rect.right()))
        local_px = x - clip_rect.left()
        seconds = clip_start + local_px / self.pixels_per_second
        seconds = self._clamp_keyframe_seconds(seconds, clip_start, clip_end)
        relative_seconds = max(0.0, seconds - clip_start)
        relative_seconds = self._apply_keyframe_snapping(drag, relative_seconds)
        seconds = clip_start + relative_seconds
        seconds = self._clamp_keyframe_seconds(seconds, clip_start, clip_end)
        seconds = self._snap_time(seconds)
        relative_seconds = max(0.0, seconds - clip_start)
        drag["pending_seconds"] = relative_seconds
        if self.fps_float:
            new_frame = int(round(seconds * self.fps_float)) + 1
        else:
            new_frame = drag.get("current_frame")
        drag["pending_frame"] = new_frame
        absolute_seconds = self._keyframe_base_position(marker) + relative_seconds
        self._panel_preview_marker(
            marker,
            drag.get("current_frame"),
            new_frame,
            absolute_seconds,
            drag_paths=drag.get("data_paths"),
        )
        if new_frame != drag.get("current_frame"):
            drag["moved"] = True
        self._seek_to_marker_frame(marker, new_frame, start_preroll=False)
        self._keyframes_dirty = True
        self.update()

    def _apply_keyframe_delta(self, drag, ignore_refresh=False, force=False):
        marker = drag.get("marker")
        if not marker:
            return
        new_frame = drag.get("pending_frame")
        old_frame = drag.get("current_frame")
        if new_frame is None or old_frame is None:
            return
        new_value = drag.get("pending_value")
        do_move = new_frame != old_frame or self._retime_drag_value_changed(drag)
        if not do_move and not force:
            return
        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            return
        transaction_id = drag.get("transaction_id")
        data_paths = tuple(drag.get("data_paths") or ())
        data_path = drag.get("data_path") if drag.get("data_path") else None
        if marker.get("type") == "transition":
            transition = marker.get("transition")
            if not transition:
                return
            data_copy = json.loads(json.dumps(transition.data))
            moved_specific = False
            target_paths = data_paths if data_paths else (() if data_path is None else (data_path,))
            if target_paths:
                for path in target_paths:
                    if path and self._set_keyframe_frame_at_path(data_copy, path, new_frame):
                        moved_specific = True
                if (do_move or force) and isinstance(transition.data, (dict, list)) and moved_specific:
                    for path in target_paths:
                        if path:
                            self._set_keyframe_frame_at_path(transition.data, path, new_frame)
            if (do_move or force) and not moved_specific:
                self._move_keyframes_in_object(data_copy, old_frame, new_frame)
                if isinstance(transition.data, (dict, list)):
                    self._move_keyframes_in_object(transition.data, old_frame, new_frame)
            timeline.update_transition_data(
                data_copy,
                only_basic_props=False,
                ignore_refresh=ignore_refresh,
                transaction_id=transaction_id,
            )
        else:
            clip = marker.get("clip")
            if not clip:
                return
            data_copy = json.loads(json.dumps(clip.data))
            moved_specific = False
            target_paths = data_paths if data_paths else (() if data_path is None else (data_path,))
            retime_curve = self._is_retime_curve_marker(marker) and new_value is not None
            if target_paths:
                for path in target_paths:
                    if not path:
                        continue
                    changed_frame = self._set_keyframe_frame_at_path(data_copy, path, new_frame)
                    changed_value = False
                    if retime_curve:
                        changed_value = self._set_keyframe_value_at_path(data_copy, path, new_value)
                    if changed_frame or changed_value:
                        moved_specific = True
                if (do_move or force) and isinstance(clip.data, (dict, list)) and moved_specific:
                    for path in target_paths:
                        if path:
                            self._set_keyframe_frame_at_path(clip.data, path, new_frame)
                            if retime_curve:
                                self._set_keyframe_value_at_path(clip.data, path, new_value)
                    if retime_curve:
                        clamp_timing_to_media(data_copy, clip)
                        clamp_timing_to_media(clip.data, clip)
            if (do_move or force) and not moved_specific:
                if marker.get("type") == "effect":
                    effect_id = marker.get("owner_id")
                    for eff in data_copy.get("effects", []):
                        if str(eff.get("id")) == str(effect_id):
                            self._move_keyframes_in_object(eff, old_frame, new_frame)
                            break
                    if isinstance(clip.data, dict):
                        for eff in clip.data.get("effects", []):
                            if str(eff.get("id")) == str(effect_id):
                                self._move_keyframes_in_object(eff, old_frame, new_frame)
                                break
                else:
                    self._move_keyframes_in_object(data_copy, old_frame, new_frame)
                    if isinstance(clip.data, (dict, list)):
                        self._move_keyframes_in_object(clip.data, old_frame, new_frame)
            timeline.update_clip_data(
                data_copy,
                only_basic_props=False,
                ignore_reader=True,
                ignore_refresh=ignore_refresh,
                transaction_id=transaction_id,
            )

        base_position = self._keyframe_base_position(marker)
        pending_seconds = drag.get("pending_seconds")
        if pending_seconds is None and self.fps_float:
            pending_seconds = max(0.0, ((new_frame - 1.0) / self.fps_float) - drag.get("clip_start", 0.0))
        absolute_seconds = base_position + (pending_seconds or 0.0)
        self._panel_preview_marker(
            marker,
            old_frame,
            new_frame,
            absolute_seconds,
            drag_paths=drag.get("data_paths"),
        )

        drag["current_frame"] = new_frame
        marker["frame"] = new_frame
        marker["display_frame"] = new_frame
        if self.fps_float:
            seconds_abs = (new_frame - 1.0) / self.fps_float
            clip_start = drag.get("clip_start", 0.0)
            marker["seconds"] = max(0.0, seconds_abs - clip_start)
            marker["display_seconds"] = marker["seconds"]
        if new_value is not None:
            drag["current_value"] = float(new_value)
            marker["curve_value"] = float(new_value)
            pending_y_ratio = drag.get("pending_y_ratio")
            if pending_y_ratio is not None:
                marker["curve_y_ratio"] = pending_y_ratio
        if do_move or force:
            drag["moved"] = True

    def _select_marker_owner(self, marker, *, seek=False, clear_existing=True):
        if not marker:
            return

        marker_type = marker.get("type")
        target_id = None
        target_type = None

        if marker_type == "effect":
            target_id = marker.get("owner_id") or marker.get("effect_id")
            target_type = "effect"
        elif marker_type == "transition":
            transition = marker.get("transition")
            if transition:
                target_id = getattr(transition, "id", None)
                target_type = "transition"
        else:
            clip = marker.get("clip")
            if clip:
                target_id = getattr(clip, "id", None)
                target_type = "clip"

        if target_id is not None and target_type:
            self._select_timeline_item(target_id, target_type, clear_existing)

        if not seek:
            return

        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            return

        clip = marker.get("clip")
        transition = marker.get("transition")
        clip_start = marker.get("clip_start", 0.0)
        frame = marker.get("frame", 1)
        fps = self.fps_float or 1.0
        base_position = 0.0
        if clip:
            data = clip.data if isinstance(clip.data, dict) else {}
            base_position = float(data.get("position", 0.0) or 0.0)
        elif transition:
            data = transition.data if isinstance(transition.data, dict) else {}
            base_position = float(data.get("position", 0.0) or 0.0)
        absolute = round(base_position * fps) + frame - round(clip_start * fps)
        absolute = max(1, int(absolute))
        timeline.SeekToKeyframe(absolute)

    def _handle_keyframe_click(self, marker, clear_existing=True):
        if not marker:
            return
        self._active_keyframe_marker = marker
        self._select_marker_owner(marker, seek=True, clear_existing=clear_existing)

    def _seek_to_marker_frame(self, marker, frame, start_preroll=True):
        if marker is None or frame is None:
            return
        fps = self.fps_float or 1.0
        clip = marker.get("clip")
        transition = marker.get("transition")
        clip_start = marker.get("clip_start", 0.0)
        base_position = 0.0
        if clip:
            data = clip.data if isinstance(clip.data, dict) else {}
            base_position = float(data.get("position", 0.0) or 0.0)
        elif transition:
            data = transition.data if isinstance(transition.data, dict) else {}
            base_position = float(data.get("position", 0.0) or 0.0)
        absolute = round(base_position * fps) + frame - round(clip_start * fps)
        absolute = max(1, int(absolute))
        self.win.SeekSignal.emit(absolute, bool(start_preroll))

    def _finishKeyframeDrag(self):
        if self._dragging_panel_keyframes:
            self._finish_panel_keyframe_drag()
            return
        drag = self._dragging_keyframe
        if not drag:
            return
        started = drag.get("transaction_started")
        changed = (
            drag.get("pending_frame") != drag.get("current_frame")
            or self._retime_drag_value_changed(drag)
        )
        moved = drag.get("moved")
        marker = drag.get("marker")
        timeline = getattr(self.win, "timeline", None)
        if moved:
            if changed:
                self._begin_keyframe_transaction()
                started = drag.get("transaction_started")
            if started:
                self._apply_keyframe_delta(drag, force=True)
                if timeline:
                    timeline.FinalizeKeyframeDrag(
                        drag.get("object_type", "clip"),
                        drag.get("object_id", ""),
                    )
                if hasattr(self.win, "show_property_timeout"):
                    QTimer.singleShot(0, self.win.show_property_timeout)
            pending_frame = drag.get("pending_frame")
            if pending_frame is not None:
                self._seek_to_marker_frame(marker, pending_frame, start_preroll=True)
        else:
            clear_existing = drag.get("clear_existing", True)
            self._handle_keyframe_click(marker, clear_existing=clear_existing)

        self._active_keyframe_marker = marker
        self._dragging_keyframe = None
        self.mouse_dragging = False
        self._keyframes_dirty = True
        self._release_cursor()
        self.update()
