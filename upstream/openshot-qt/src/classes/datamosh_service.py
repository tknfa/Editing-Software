"""
 @file
 @brief Cached datamosh generation service for derived clip assets.
"""

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

try:
    import openshot
    _OPENSHOT_IMPORT_ERROR = None
except ImportError as exc:
    _OPENSHOT_IMPORT_ERROR = exc

    class _OpenShotFallback:
        LAYOUT_STEREO = 3

    openshot = _OpenShotFallback()
from PyQt5.QtCore import QObject, QPointF, pyqtSignal

from classes import info
from classes.app import get_app
from classes.logger import log
from classes.path_utils import absolute_media_path
from classes.query import Clip, File, Track, Transition
from classes.ui_text import sanitize_ui_text


DATAMOSH_CACHE_VERSION = "v1"
DATAMOSH_MIN_DURATION_SECONDS = 0.5
DATAMOSH_HISTORY_LIMIT = 4
DATAMOSH_AMOUNT_DEFAULT_KEY = "default"
DATAMOSH_AMOUNT_ORDER = (
    "light",
    DATAMOSH_AMOUNT_DEFAULT_KEY,
    "wild",
)
DATAMOSH_HISTORY_UI_KEY = "datamosh_history"
DATAMOSH_SOURCE_CLIP_UI_KEY = "datamosh_source_clip_id"
DATAMOSH_HISTORY_ID_UI_KEY = "datamosh_history_id"
DATAMOSH_PRESET_UI_KEY = "datamosh_preset_key"
DATAMOSH_AMOUNT_UI_KEY = "datamosh_amount_key"
DATAMOSH_RENDER_CACHE_CLEAR_INTERVAL = 24
DATAMOSH_PRESET_ORDER = (
    "cut_mosh",
    "classic_melt",
    "repeat_melt",
    "jiggle_pulse",
)
DATAMOSH_AMOUNT_PRESETS = {
    "light": {
        "label": "Light",
    },
    DATAMOSH_AMOUNT_DEFAULT_KEY: {
        "label": "Default",
    },
    "wild": {
        "label": "Wild",
    },
}
DATAMOSH_PRESETS = {
    "cut_mosh": {
        "label": "Cut Mosh",
        "description": "Signature drifting cuts",
        "worker_mode": "void_cut",
        "preprocess_family": "x264_fixed",
    },
    "classic_melt": {
        "label": "Classic Melt",
        "description": "I-frame removal wash",
        "worker_mode": "classic_melt",
        "preprocess_family": "mpeg4_mosh",
    },
    "repeat_melt": {
        "label": "Repeat Melt",
        "description": "Delta-frame smears",
        "worker_mode": "repeat_melt",
        "preprocess_family": "mpeg4_mosh",
    },
    "jiggle_pulse": {
        "label": "Jiggle Pulse",
        "description": "Loose dancing vectors",
        "worker_mode": "jiggle_pulse",
        "preprocess_family": "x264_fixed",
    },
}
_DATAMOSH_CACHE_UI_IGNORE_KEYS = {
    DATAMOSH_HISTORY_UI_KEY,
    DATAMOSH_SOURCE_CLIP_UI_KEY,
    DATAMOSH_HISTORY_ID_UI_KEY,
    DATAMOSH_PRESET_UI_KEY,
    DATAMOSH_AMOUNT_UI_KEY,
}


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def clip_source_path(clip_data):
    """Return the selected clip's absolute source path."""
    reader = clip_data.get("reader") if isinstance(clip_data, dict) else None
    if not isinstance(reader, dict):
        return ""
    return absolute_media_path(reader.get("path"))


def clip_has_video_source(clip_data):
    reader = clip_data.get("reader") if isinstance(clip_data, dict) else None
    if not isinstance(reader, dict):
        return False
    has_video = reader.get("has_video")
    if has_video is None:
        has_video = True
    return bool(has_video) and not bool(reader.get("has_single_image"))


def clip_visible_duration_seconds(clip_data):
    """Return the clip's visible source-trimmed duration in seconds."""
    if not isinstance(clip_data, dict):
        return 0.0
    start_s = _safe_float(clip_data.get("start", 0.0))
    end_s = _safe_float(clip_data.get("end", start_s), start_s)
    duration_s = end_s - start_s
    if duration_s <= 0.0:
        duration_s = _safe_float(clip_data.get("duration", 0.0))
    return max(0.0, duration_s)


def clip_timeline_span(clip_data):
    """Return (left, right, duration) for the clip on the timeline."""
    left_edge = _safe_float(clip_data.get("position", 0.0))
    duration_s = clip_visible_duration_seconds(clip_data)
    return left_edge, left_edge + duration_s, duration_s


def sanitize_filename_component(value):
    """Convert a display string into a stable filename-safe component."""
    text = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip()).strip("-").lower()
    return text[:32] or "clip"


def normalize_datamosh_amount_key(amount_key):
    normalized = str(amount_key or DATAMOSH_AMOUNT_DEFAULT_KEY)
    if normalized not in DATAMOSH_AMOUNT_PRESETS:
        return DATAMOSH_AMOUNT_DEFAULT_KEY
    return normalized


def datamosh_amount_label(amount_key):
    amount_key = normalize_datamosh_amount_key(amount_key)
    return str(DATAMOSH_AMOUNT_PRESETS.get(amount_key, {}).get("label") or amount_key.title())


def format_datamosh_variant_label(preset_key, amount_key):
    preset = DATAMOSH_PRESETS.get(preset_key, {})
    preset_label = str(preset.get("label") or preset_key or "Datamosh")
    amount_key = normalize_datamosh_amount_key(amount_key)
    if amount_key == DATAMOSH_AMOUNT_DEFAULT_KEY:
        return preset_label
    return "{} ({})".format(preset_label, datamosh_amount_label(amount_key))


def build_datamosh_preprocess_args(preset_key, amount_key):
    """Return ffmpeg preprocess args for one preset/amount combination."""
    preset = DATAMOSH_PRESETS.get(preset_key, {})
    amount_key = normalize_datamosh_amount_key(amount_key)
    family = str(preset.get("preprocess_family") or "")

    if family == "mpeg4_mosh":
        qscale = {
            "light": "4",
            DATAMOSH_AMOUNT_DEFAULT_KEY: "2",
            "wild": "1",
        }[amount_key]
        return [
            "-an",
            "-c:v", "mpeg4",
            "-bf", "0",
            "-qscale:v", qscale,
        ]

    bitrate = {
        "light": "3M",
        DATAMOSH_AMOUNT_DEFAULT_KEY: "2M",
        "wild": "1M",
    }[amount_key]
    return [
        "-an",
        "-c:v", "libx264",
        "-preset", "medium",
        "-b:v", bitrate,
        "-minrate", bitrate,
        "-maxrate", bitrate,
        "-bufsize", bitrate,
    ]


def build_datamosh_cache_key(source_path, clip_data, preset_key, source_mtime=None, amount_key=DATAMOSH_AMOUNT_DEFAULT_KEY):
    """Build a stable cache key for one preset + edited clip request."""
    payload = {
        "version": DATAMOSH_CACHE_VERSION,
        "preset_key": str(preset_key or ""),
        "amount_key": normalize_datamosh_amount_key(amount_key),
        "source_path": os.path.normpath(str(source_path or "")),
        "source_mtime": float(source_mtime or 0.0),
        "render_signature": build_datamosh_render_signature(clip_data),
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def build_datamosh_output_path(
    cache_root,
    source_title,
    preset_key,
    cache_key,
    amount_key=DATAMOSH_AMOUNT_DEFAULT_KEY,
):
    """Return the cached output path for one derived datamosh asset."""
    preset = DATAMOSH_PRESETS.get(preset_key, {})
    preset_slug = sanitize_filename_component(preset.get("label") or preset_key)
    title_slug = sanitize_filename_component(source_title)
    amount_key = normalize_datamosh_amount_key(amount_key)
    if amount_key != DATAMOSH_AMOUNT_DEFAULT_KEY:
        preset_slug = "{}-{}".format(preset_slug, sanitize_filename_component(datamosh_amount_label(amount_key)))
    filename = "{}-{}-{}.mp4".format(title_slug, preset_slug, str(cache_key)[:10])
    return os.path.join(cache_root, filename)


def build_datamosh_temp_output_path(output_path):
    """Return a temporary output path that preserves the final media extension."""
    root, ext = os.path.splitext(str(output_path or ""))
    ext = ext or ".mp4"
    return "{}.tmp{}".format(root or str(output_path or ""), ext)


def build_datamosh_history_entry(
    preset_key,
    output_path,
    source_title,
    *,
    amount_key=DATAMOSH_AMOUNT_DEFAULT_KEY,
    generated_clip_id="",
    file_id="",
    track_number=None,
    position=None,
):
    """Return a compact recent-history entry for one generated datamosh asset."""
    preset = DATAMOSH_PRESETS.get(preset_key, {})
    try:
        normalized_position = float(position) if position is not None else None
    except (TypeError, ValueError):
        normalized_position = None
    try:
        normalized_track = int(track_number) if track_number is not None else None
    except (TypeError, ValueError):
        normalized_track = None

    return {
        "id": os.path.basename(str(output_path or "")) or "{}:{}".format(source_title, preset_key),
        "preset_key": str(preset_key or ""),
        "preset_label": str(preset.get("label") or preset_key or "Datamosh"),
        "amount_key": normalize_datamosh_amount_key(amount_key),
        "amount_label": datamosh_amount_label(amount_key),
        "output_path": str(output_path or ""),
        "source_title": str(source_title or "Clip"),
        "generated_clip_id": str(generated_clip_id or ""),
        "file_id": str(file_id or ""),
        "track_number": normalized_track,
        "position": normalized_position,
    }


def merge_datamosh_history(entries, new_entry, limit=DATAMOSH_HISTORY_LIMIT):
    """Move one history entry to the front, de-duplicated by id/output path."""
    if not isinstance(new_entry, dict):
        return list(entries or [])[: max(0, int(limit or 0))]

    history_id = str(new_entry.get("id") or "")
    output_path = str(new_entry.get("output_path") or "")
    merged = [copy.deepcopy(new_entry)]
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        if history_id and str(entry.get("id") or "") == history_id:
            continue
        if output_path and str(entry.get("output_path") or "") == output_path:
            continue
        merged.append(copy.deepcopy(entry))
    if limit and int(limit) > 0:
        return merged[: int(limit)]
    return merged


def _clip_ui_data(clip_data, create=False):
    if not isinstance(clip_data, dict):
        return None
    ui_data = clip_data.get("ui")
    if isinstance(ui_data, dict):
        return ui_data
    if create:
        ui_data = {}
        clip_data["ui"] = ui_data
        return ui_data
    return None


def build_datamosh_render_signature(clip_data):
    """Return clip data that should influence edited-result cache invalidation."""
    if not isinstance(clip_data, dict):
        return {}

    signature = copy.deepcopy(clip_data)
    ui_data = signature.get("ui")
    if isinstance(ui_data, dict):
        filtered_ui = {
            str(key): copy.deepcopy(value)
            for key, value in ui_data.items()
            if key not in _DATAMOSH_CACHE_UI_IGNORE_KEYS
        }
        if filtered_ui:
            signature["ui"] = filtered_ui
        else:
            signature.pop("ui", None)
    return signature


def _normalized_fraction_dict(data, default_num, default_den=1):
    fraction = data if isinstance(data, dict) else {}
    num = _safe_int(fraction.get("num", default_num), default_num)
    den = _safe_int(fraction.get("den", default_den), default_den)
    if den <= 0:
        den = int(default_den or 1)
    if num <= 0:
        num = int(default_num or 1)
    return {"num": num, "den": den}


def build_datamosh_render_settings(project_data):
    """Return a render-safe snapshot of project profile settings."""
    project_data = project_data if isinstance(project_data, dict) else {}
    return {
        "width": max(2, _safe_int(project_data.get("width", 2), 2)),
        "height": max(2, _safe_int(project_data.get("height", 2), 2)),
        "fps": _normalized_fraction_dict(project_data.get("fps"), 30, 1),
        "pixel_ratio": _normalized_fraction_dict(project_data.get("pixel_ratio"), 1, 1),
        "sample_rate": max(1, _safe_int(project_data.get("sample_rate", 48000), 48000)),
        "channels": max(1, _safe_int(project_data.get("channels", 2), 2)),
        "channel_layout": _safe_int(project_data.get("channel_layout", openshot.LAYOUT_STEREO), openshot.LAYOUT_STEREO),
        "has_audio": bool(project_data.get("has_audio", True)),
        "has_video": bool(project_data.get("has_video", True)),
    }


def build_datamosh_render_project(project_data, clip_data):
    """Return an isolated project snapshot that preserves the selected clip's edits."""
    project_payload = copy.deepcopy(project_data if isinstance(project_data, dict) else {})
    selected_clip = copy.deepcopy(clip_data if isinstance(clip_data, dict) else {})
    clip_id = str(selected_clip.get("id") or "")

    if clip_id:
        project_clips = [
            copy.deepcopy(item)
            for item in (project_payload.get("clips") or [])
            if isinstance(item, dict) and str(item.get("id") or "") == clip_id
        ]
    else:
        project_clips = []
    if not project_clips and selected_clip:
        project_clips = [selected_clip]

    project_payload["clips"] = project_clips
    project_payload["effects"] = []
    project_payload["markers"] = []
    project_payload["history"] = {"undo": [], "redo": []}

    layer_number = _safe_int((project_clips[0] if project_clips else selected_clip).get("layer", 0), 0)
    project_layers = [
        copy.deepcopy(layer)
        for layer in (project_payload.get("layers") or [])
        if isinstance(layer, dict) and _safe_int(layer.get("number", 0), 0) == layer_number
    ]
    if not project_layers:
        project_layers = [{"number": layer_number, "y": 0, "label": "Datamosh Render", "lock": False}]
    project_payload["layers"] = project_layers
    return project_payload


def datamosh_render_frame_range(clip_data, render_settings):
    """Return the project frame range that covers the selected clip span."""
    fps_data = (render_settings or {}).get("fps")
    fps_num = float((fps_data or {}).get("num", 30) or 30)
    fps_den = float((fps_data or {}).get("den", 1) or 1)
    fps_float = (fps_num / fps_den) if fps_num > 0.0 and fps_den > 0.0 else 30.0
    frame_duration = 1.0 / fps_float

    position = _safe_float((clip_data or {}).get("position", 0.0))
    duration = clip_visible_duration_seconds(clip_data or {})
    start_frame = max(1, int(round(position * fps_float)) + 1)
    end_seconds = position + max(0.0, duration - frame_duration)
    end_frame = max(start_frame, int(round(end_seconds * fps_float)) + 1)
    return start_frame, end_frame


def get_persisted_datamosh_history(clip_data):
    """Return recent datamosh history saved on a source clip."""
    ui_data = _clip_ui_data(clip_data, create=False)
    history = ui_data.get(DATAMOSH_HISTORY_UI_KEY) if isinstance(ui_data, dict) else None
    if not isinstance(history, list):
        return []
    return [copy.deepcopy(entry) for entry in history if isinstance(entry, dict)]


def set_persisted_datamosh_history(clip_data, entries):
    """Persist recent datamosh history on a source clip."""
    if not isinstance(clip_data, dict):
        return False
    ui_data = _clip_ui_data(clip_data, create=True)
    ui_data[DATAMOSH_HISTORY_UI_KEY] = [copy.deepcopy(entry) for entry in (entries or []) if isinstance(entry, dict)]
    return True


def get_persisted_datamosh_source_clip_id(clip_data):
    """Return the saved source clip id for a generated datamosh variant."""
    ui_data = _clip_ui_data(clip_data, create=False)
    source_clip_id = ui_data.get(DATAMOSH_SOURCE_CLIP_UI_KEY) if isinstance(ui_data, dict) else None
    return str(source_clip_id or "")


def get_persisted_datamosh_amount_key(clip_data):
    """Return the saved amount key for a generated datamosh variant."""
    ui_data = _clip_ui_data(clip_data, create=False)
    amount_key = ui_data.get(DATAMOSH_AMOUNT_UI_KEY) if isinstance(ui_data, dict) else None
    return normalize_datamosh_amount_key(amount_key)


def set_persisted_datamosh_generated_metadata(clip_data, source_clip_id, entry):
    """Tag a generated clip with the source clip and history entry it belongs to."""
    if not isinstance(clip_data, dict):
        return False
    ui_data = _clip_ui_data(clip_data, create=True)
    ui_data[DATAMOSH_SOURCE_CLIP_UI_KEY] = str(source_clip_id or "")
    if isinstance(entry, dict):
        ui_data[DATAMOSH_HISTORY_ID_UI_KEY] = str(entry.get("id") or "")
        ui_data[DATAMOSH_PRESET_UI_KEY] = str(entry.get("preset_key") or "")
        ui_data[DATAMOSH_AMOUNT_UI_KEY] = normalize_datamosh_amount_key(entry.get("amount_key"))
    return True


def resolve_datamosh_clip_target(selection, clip_lookup=None, tr=None):
    """Resolve a single eligible clip target for the datamosh dock."""
    tr = tr or (lambda text: text)
    clip_lookup = clip_lookup or (lambda clip_id: Clip.get(id=clip_id))
    selection = [sel for sel in (selection or []) if isinstance(sel, dict)]
    clip_ids = [sel.get("id") for sel in selection if sel.get("type") == "clip" and sel.get("id")]

    default_message = tr("Select one video clip to generate a datamoshed version.")
    if len(clip_ids) != 1:
        return {"enabled": False, "clip_id": None, "message": default_message}

    clip = clip_lookup(clip_ids[0])
    clip_data = getattr(clip, "data", None) if clip else None
    if not isinstance(clip_data, dict):
        return {"enabled": False, "clip_id": None, "message": default_message}
    if not clip_has_video_source(clip_data):
        return {
            "enabled": False,
            "clip_id": clip_ids[0],
            "message": tr("Datamosh generation needs a video clip, not audio-only or still-image media."),
        }

    source_path = clip_source_path(clip_data)
    if not source_path or not os.path.exists(source_path):
        return {
            "enabled": False,
            "clip_id": clip_ids[0],
            "message": tr("The selected clip's source file is missing."),
        }

    duration_s = clip_visible_duration_seconds(clip_data)
    if duration_s < DATAMOSH_MIN_DURATION_SECONDS:
        return {
            "enabled": False,
            "clip_id": clip_ids[0],
            "message": tr("Choose a clip at least %(seconds).1f seconds long.") % {
                "seconds": DATAMOSH_MIN_DURATION_SECONDS
            },
        }

    title = clip.title() if clip and callable(getattr(clip, "title", None)) else os.path.basename(source_path)
    title = sanitize_ui_text(title)
    return {
        "enabled": True,
        "clip_id": clip_ids[0],
        "title": title,
        "duration": duration_s,
        "source_path": source_path,
        "message": tr("Pick a preset to create a cached moshed clip from this edited clip."),
        "summary": tr("Selected clip - %(title)s") % {"title": title},
    }


class DatamoshService(QObject):
    """Generate cached datamosh assets in the background and place them on the timeline."""

    job_updated = pyqtSignal(str, str, str)
    job_finished = pyqtSignal(str, str, object)
    ACTIVE_STATES = {"queued", "running"}

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="datamosh")
        self._lock = threading.RLock()
        self._jobs = {}
        self._states = {}
        self._history = {}
        self._generated_sources = {}
        self.job_finished.connect(self._on_job_finished)

    def shutdown(self):
        executor = getattr(self, "_executor", None)
        if executor:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                executor.shutdown(wait=False)
            self._executor = None

    def get_clip_state(self, clip_id):
        with self._lock:
            return copy.deepcopy(self._states.get(str(clip_id or ""), {}))

    def resolve_history_source_clip_id(self, clip_id):
        """Return the source clip id that owns datamosh history for a selected clip."""
        clip_id = str(clip_id or "")
        if not clip_id:
            return ""
        with self._lock:
            source_clip_id = str(self._generated_sources.get(clip_id) or "")
        if source_clip_id:
            return source_clip_id

        clip = Clip.get(id=clip_id)
        clip_data = clip.data if clip and isinstance(clip.data, dict) else None
        source_clip_id = get_persisted_datamosh_source_clip_id(clip_data)
        if source_clip_id:
            with self._lock:
                self._generated_sources[clip_id] = source_clip_id
            return source_clip_id
        return clip_id

    def get_clip_history(self, clip_id):
        """Return the most recent generated variants for one source clip."""
        source_clip_id = self.resolve_history_source_clip_id(clip_id)
        if not source_clip_id:
            return []
        with self._lock:
            history = copy.deepcopy(self._history.get(source_clip_id, []))
        if history:
            return history

        clip = Clip.get(id=source_clip_id)
        clip_data = clip.data if clip and isinstance(clip.data, dict) else None
        history = get_persisted_datamosh_history(clip_data)
        if history:
            with self._lock:
                self._history[source_clip_id] = copy.deepcopy(history)
                for entry in history:
                    generated_clip_id = str(entry.get("generated_clip_id") or "")
                    if generated_clip_id:
                        self._generated_sources[generated_clip_id] = source_clip_id
        return history

    def generate_for_clip(self, clip_id, preset_key, amount_key=DATAMOSH_AMOUNT_DEFAULT_KEY):
        clip_id = str(clip_id or "")
        amount_key = normalize_datamosh_amount_key(amount_key)
        preset = DATAMOSH_PRESETS.get(preset_key)
        if not clip_id or not preset:
            return False
        variant_label = format_datamosh_variant_label(preset_key, amount_key)

        target = resolve_datamosh_clip_target(
            [{"id": clip_id, "type": "clip"}],
            tr=get_app()._tr,
        )
        if not target.get("enabled"):
            self._set_state(clip_id, "error", str(target.get("message") or ""))
            return False

        with self._lock:
            active = self._jobs.get(clip_id)
            if active and active.get("status") in self.ACTIVE_STATES:
                self._set_state(
                    clip_id,
                    str(active.get("status") or "running"),
                    get_app()._tr("Datamosh generation is already running for this clip."),
                    preset_key=str(active.get("preset_key") or preset_key),
                )
                return False

        cache_root = self._cache_root()
        os.makedirs(cache_root, exist_ok=True)
        source_mtime = os.path.getmtime(target["source_path"]) if os.path.exists(target["source_path"]) else 0.0
        clip = Clip.get(id=clip_id)
        clip_data = copy.deepcopy(clip.data if clip else {})
        project_data = copy.deepcopy(getattr(get_app().project, "_data", {}) or {})
        render_settings = build_datamosh_render_settings(project_data)
        cache_key = build_datamosh_cache_key(
            target["source_path"],
            clip_data,
            preset_key,
            source_mtime,
            amount_key=amount_key,
        )
        output_path = build_datamosh_output_path(
            cache_root,
            target["title"],
            preset_key,
            cache_key,
            amount_key=amount_key,
        )

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            self._set_state(
                clip_id,
                "cached",
                get_app()._tr("Using cached %(preset)s result.") % {"preset": variant_label},
                preset_key=preset_key,
            )
            self.job_finished.emit(
                clip_id,
                "cached",
                {
                    "preset_key": preset_key,
                    "amount_key": amount_key,
                    "output_path": output_path,
                    "source_title": target["title"],
                },
            )
            return True

        self._set_state(
            clip_id,
            "running",
            get_app()._tr("Generating %(preset)s...") % {"preset": variant_label},
            preset_key=preset_key,
        )
        future = self._executor.submit(
            self._render_datamosh_asset,
            clip_id,
            clip_data,
            project_data,
            render_settings,
            preset_key,
            amount_key,
            output_path,
            target["title"],
        )
        with self._lock:
            self._jobs[clip_id] = {
                "status": "running",
                "preset_key": preset_key,
                "amount_key": amount_key,
                "future": future,
                "output_path": output_path,
            }
        future.add_done_callback(lambda fut, selected_clip_id=clip_id: self._emit_result(selected_clip_id, fut))
        return True

    def _set_state(self, clip_id, status, message, preset_key=None):
        payload = {"status": str(status or ""), "message": str(message or "")}
        if preset_key:
            payload["preset_key"] = str(preset_key)
        with self._lock:
            self._states[str(clip_id or "")] = payload
        self.job_updated.emit(str(clip_id or ""), payload["status"], payload["message"])

    def _remember_history_entry(self, clip_id, entry):
        clip_id = str(clip_id or "")
        if not clip_id or not isinstance(entry, dict):
            return []
        with self._lock:
            merged = merge_datamosh_history(self._history.get(clip_id, []), entry, DATAMOSH_HISTORY_LIMIT)
            self._history[clip_id] = merged
            generated_clip_id = str(entry.get("generated_clip_id") or "")
            if generated_clip_id:
                self._generated_sources[generated_clip_id] = clip_id
        self._persist_history_for_source_clip(clip_id, merged)
        generated_clip_id = str(entry.get("generated_clip_id") or "")
        if generated_clip_id:
            self._persist_generated_clip_link(generated_clip_id, clip_id, merged[0])
        return merged

    def _persist_history_for_source_clip(self, clip_id, history_entries):
        source_clip = Clip.get(id=clip_id)
        if not source_clip or not isinstance(source_clip.data, dict):
            return
        try:
            set_persisted_datamosh_history(source_clip.data, history_entries)
            source_clip.save()
        except Exception as exc:
            log.debug("Unable to persist datamosh history for clip %s: %s", clip_id, exc, exc_info=True)

    def _persist_generated_clip_link(self, generated_clip_id, source_clip_id, entry):
        generated_clip = Clip.get(id=generated_clip_id)
        if not generated_clip or not isinstance(generated_clip.data, dict):
            return
        try:
            set_persisted_datamosh_generated_metadata(generated_clip.data, source_clip_id, entry)
            generated_clip.save()
        except Exception as exc:
            log.debug(
                "Unable to persist datamosh source link for clip %s: %s",
                generated_clip_id,
                exc,
                exc_info=True,
            )

    def _emit_result(self, clip_id, future):
        try:
            payload = future.result()
        except Exception as exc:
            log.warning("Datamosh job failed for clip %s: %s", clip_id, exc, exc_info=True)
            self.job_finished.emit(
                str(clip_id or ""),
                "failed",
                {"error": str(exc or "Datamosh job failed.")},
            )
            return
        self.job_finished.emit(str(clip_id or ""), "completed", payload)

    def _worker_script_path(self):
        return os.path.join(info.PATH, "tools", "datamosh_worker.py")

    def _cache_root(self):
        return os.path.join(info.CACHE_PATH, "datamosh")

    def _jobs_root(self):
        return os.path.join(self._cache_root(), "jobs")

    def _ffmpeg_path(self):
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return ffmpeg_path
        try:
            import imageio_ffmpeg  # type: ignore
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:
            raise RuntimeError("ffmpeg is not available on this system.") from exc

    def _run_command(self, args, cwd=None):
        log.debug("Datamosh command: %s", " ".join(str(arg) for arg in args))
        process = subprocess.run(
            [str(arg) for arg in args],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if process.returncode != 0:
            error_text = (process.stderr or process.stdout or "").strip()
            if not error_text:
                error_text = "Command failed with exit code {}".format(process.returncode)
            raise RuntimeError(error_text)
        return process

    @staticmethod
    def _clear_cache_object(cache_object):
        if not cache_object:
            return
        try:
            cache_object.Clear()
        except Exception:
            log.debug("Datamosh render cache clear failed", exc_info=1)

    def _render_timeline_range_to_file(self, project_data, render_settings, output_path, start_frame, end_frame):
        """Render one project frame range to an intermediate file."""
        if not hasattr(openshot, "Timeline"):
            raise RuntimeError("libopenshot Python bindings are not available.") from _OPENSHOT_IMPORT_ERROR
        render_settings = render_settings if isinstance(render_settings, dict) else {}
        fps = _normalized_fraction_dict(render_settings.get("fps"), 30, 1)
        pixel_ratio = _normalized_fraction_dict(render_settings.get("pixel_ratio"), 1, 1)
        width = max(2, _safe_int(render_settings.get("width", 2), 2))
        height = max(2, _safe_int(render_settings.get("height", 2), 2))
        sample_rate = max(1, _safe_int(render_settings.get("sample_rate", 48000), 48000))
        channels = max(1, _safe_int(render_settings.get("channels", 2), 2))
        channel_layout = _safe_int(render_settings.get("channel_layout", openshot.LAYOUT_STEREO), openshot.LAYOUT_STEREO)

        timeline = openshot.Timeline(
            width,
            height,
            openshot.Fraction(int(fps["num"]), int(fps["den"])),
            sample_rate,
            channels,
            channel_layout,
        )
        timeline.info.sample_rate = sample_rate
        timeline.info.channels = channels
        timeline.info.channel_layout = channel_layout
        timeline.info.has_audio = bool(render_settings.get("has_audio", True))
        timeline.info.has_video = bool(render_settings.get("has_video", True))

        writer = None
        try:
            timeline.SetJson(json.dumps(project_data or {}))
            timeline.Open()

            writer = openshot.FFmpegWriter(output_path)
            writer.SetVideoOptions(
                True,
                "libx264",
                openshot.Fraction(int(fps["num"]), int(fps["den"])),
                width,
                height,
                openshot.Fraction(int(pixel_ratio["num"]), int(pixel_ratio["den"])),
                False,
                False,
                18,
            )
            writer.PrepareStreams()
            writer.Open()

            start_frame = max(1, _safe_int(start_frame, 1))
            end_frame = max(start_frame, _safe_int(end_frame, start_frame))
            for frame_number in range(start_frame, end_frame + 1):
                writer.WriteFrame(timeline.GetFrame(frame_number))
                if frame_number % int(DATAMOSH_RENDER_CACHE_CLEAR_INTERVAL) == 0:
                    try:
                        timeline.ClearAllCache(True)
                    except Exception:
                        log.debug("Datamosh render timeline cache clear failed", exc_info=1)
        finally:
            if writer:
                try:
                    writer.Close()
                except Exception:
                    log.debug("Datamosh render writer close failed", exc_info=1)
            try:
                timeline.ClearAllCache(True)
            except Exception:
                log.debug("Datamosh render final cache clear failed", exc_info=1)
            self._clear_cache_object(getattr(timeline, "GetCache", lambda: None)())
            try:
                timeline.Close()
            except Exception:
                log.debug("Datamosh render timeline close failed", exc_info=1)

    def _render_datamosh_asset(self, clip_id, clip_data, project_data, render_settings, preset_key, amount_key, output_path, source_title):
        ffmpeg_path = self._ffmpeg_path()
        worker_script = self._worker_script_path()
        if not os.path.exists(worker_script):
            raise RuntimeError("Datamosh worker script is missing.")

        preset = DATAMOSH_PRESETS[preset_key]
        amount_key = normalize_datamosh_amount_key(amount_key)
        source_path = clip_source_path(clip_data)
        if not source_path or not os.path.exists(source_path):
            raise RuntimeError("The selected clip's source file is missing.")

        trim_duration = clip_visible_duration_seconds(clip_data)
        if trim_duration < DATAMOSH_MIN_DURATION_SECONDS:
            raise RuntimeError("The selected clip is too short to datamosh.")

        jobs_root = self._jobs_root()
        os.makedirs(jobs_root, exist_ok=True)
        temp_dir = tempfile.mkdtemp(prefix="datamosh-", dir=jobs_root)
        rendered_path = os.path.join(temp_dir, "rendered.mp4")
        input_path = os.path.join(temp_dir, "input.avi")
        corrupted_path = os.path.join(temp_dir, "corrupted.avi")
        temp_output_path = build_datamosh_temp_output_path(output_path)

        try:
            render_project = build_datamosh_render_project(project_data, clip_data)
            start_frame, end_frame = datamosh_render_frame_range(clip_data, render_settings)
            self._render_timeline_range_to_file(
                render_project,
                render_settings,
                rendered_path,
                start_frame,
                end_frame,
            )

            self._run_command(
                [
                    ffmpeg_path,
                    "-loglevel", "error",
                    "-i", rendered_path,
                    *build_datamosh_preprocess_args(preset_key, amount_key),
                    "-y",
                    input_path,
                ]
            )

            self._run_command(
                [
                    sys.executable,
                    worker_script,
                    preset["worker_mode"],
                    "--amount",
                    amount_key,
                    input_path,
                    corrupted_path,
                ],
                cwd=temp_dir,
            )

            self._run_command(
                [
                    ffmpeg_path,
                    "-loglevel", "error",
                    "-fflags", "+genpts",
                    "-i", corrupted_path,
                    "-an",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    "-y",
                    temp_output_path,
                ]
            )
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            os.replace(temp_output_path, output_path)
        finally:
            if os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                except OSError:
                    pass
            shutil.rmtree(temp_dir, ignore_errors=True)

        if not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
            raise RuntimeError("Datamosh generation finished without creating an output file.")

        return {
            "clip_id": clip_id,
            "preset_key": preset_key,
            "amount_key": amount_key,
            "output_path": output_path,
            "source_title": source_title,
        }

    def _nearest_available_track_above(self, source_clip_data):
        source_layer = int(_safe_float(source_clip_data.get("layer", 0)))
        source_left, source_right, _duration = clip_timeline_span(source_clip_data)
        tracks = sorted(get_app().project.get("layers") or [], key=lambda track: track.get("number", 0))
        candidate_numbers = [int(track.get("number", 0)) for track in tracks if int(track.get("number", 0)) > source_layer]

        def overlaps_existing(track_number):
            items = Clip.filter(layer=track_number) + Transition.filter(layer=track_number)
            for item in items:
                item_data = item.data if isinstance(item.data, dict) else {}
                item_left, item_right, item_duration = clip_timeline_span(item_data)
                if item_duration <= 0.0:
                    continue
                if item_left < source_right and item_right > source_left:
                    return True
            return False

        for track_number in candidate_numbers:
            if not overlaps_existing(track_number):
                return track_number

        max_number = max(candidate_numbers + [source_layer])
        new_track_number = max_number + 1000000
        track = Track()
        track.data = {"number": new_track_number, "y": 0, "label": "Datamosh", "lock": False}
        track.save()
        return new_track_number

    def _find_existing_generated_clip(self, file_id, position, track_number, tolerance=0.01):
        for clip in Clip.filter(file_id=file_id):
            clip_data = clip.data if isinstance(clip.data, dict) else {}
            if int(_safe_float(clip_data.get("layer", -1), -1)) != int(track_number):
                continue
            if abs(_safe_float(clip_data.get("position", 0.0)) - float(position)) <= float(tolerance):
                return clip
        return None

    def _find_history_generated_clip(self, source_clip_id, entry, file_id, source_position):
        generated_clip_id = str((entry or {}).get("generated_clip_id") or "")
        if generated_clip_id:
            generated_clip = Clip.get(id=generated_clip_id)
            if generated_clip and str(generated_clip.data.get("file_id") or "") == str(file_id or ""):
                return generated_clip

        best_clip = None
        best_score = None
        expected_track = (entry or {}).get("track_number")
        for clip in Clip.filter(file_id=file_id):
            clip_data = clip.data if isinstance(clip.data, dict) else {}
            clip_position = _safe_float(clip_data.get("position", 0.0))
            mapped_source = self.resolve_history_source_clip_id(clip.id)
            score = (
                0 if mapped_source == str(source_clip_id or "") else 1,
                0 if expected_track is not None and int(_safe_float(clip_data.get("layer", -1), -1)) == int(expected_track) else 1,
                abs(clip_position - float(source_position or 0.0)),
            )
            if best_clip is None or score < best_score:
                best_clip = clip
                best_score = score
        return best_clip

    def _import_output_file(self, output_path, display_name):
        file_obj = File.get(path=output_path)
        if not file_obj:
            self.win.files_model.add_files(
                [output_path],
                quiet=True,
                prevent_image_seq=True,
                prevent_recent_folder=True,
            )
            file_obj = File.get(path=output_path)
        if not file_obj:
            raise RuntimeError("Failed to import the generated datamosh clip.")

        if file_obj.data.get("name") != display_name:
            file_obj.data["name"] = display_name
            file_obj.save()
        return file_obj

    def _select_clip(self, clip_id):
        timeline = getattr(self.win, "timeline", None)
        if not timeline or not clip_id:
            return
        timeline.ClearAllSelections()
        timeline.AddSelectionJS(str(clip_id), "clip", clear_existing=True)

    def recall_history_entry(self, clip_id, history_id):
        """Select or restore one recent generated variant for the selected clip."""
        source_clip_id = self.resolve_history_source_clip_id(clip_id)
        if not source_clip_id or not history_id:
            return False

        entries = self.get_clip_history(source_clip_id)
        entry = next((candidate for candidate in entries if str(candidate.get("id") or "") == str(history_id)), None)
        if not entry:
            return False

        output_path = str(entry.get("output_path") or "")
        if not output_path or not os.path.exists(output_path):
            self._set_state(
                source_clip_id,
                "error",
                get_app()._tr("The cached datamosh file is missing."),
                preset_key=entry.get("preset_key"),
            )
            return False

        source_clip = Clip.get(id=source_clip_id)
        source_clip_data = source_clip.data if source_clip and isinstance(source_clip.data, dict) else None
        source_position = _safe_float(
            (source_clip_data or {}).get("position", entry.get("position", 0.0)),
            _safe_float(entry.get("position", 0.0)),
        )

        try:
            amount_key = normalize_datamosh_amount_key(entry.get("amount_key"))
            display_name = "{} - {}".format(
                str(entry.get("source_title") or "Clip"),
                format_datamosh_variant_label(entry.get("preset_key"), amount_key),
            )
            file_obj = self._import_output_file(output_path, display_name)
            generated_clip = self._find_history_generated_clip(
                source_clip_id,
                entry,
                file_obj.id,
                source_position,
            )
            restored = False
            if generated_clip:
                generated_clip_id = generated_clip.id
                track_number = int(_safe_float(generated_clip.data.get("layer", 0), 0))
            else:
                if not source_clip_data:
                    raise RuntimeError("The source clip is no longer available to restore this variant.")
                track_number = self._nearest_available_track_above(source_clip_data)
                new_clip = self.win.timeline.addClip(
                    file_obj.id,
                    QPointF(source_position, 0.0),
                    track_number,
                    ignore_refresh=False,
                    call_manual_move=False,
                )
                generated_clip_id = new_clip.get("id") if isinstance(new_clip, dict) else ""
                restored = True
            self._select_clip(generated_clip_id)
        except Exception as exc:
            log.warning("Failed to recall datamosh history for clip %s: %s", source_clip_id, exc, exc_info=True)
            self._set_state(
                source_clip_id,
                "error",
                str(exc or get_app()._tr("Failed to restore the cached datamosh clip.")),
                preset_key=entry.get("preset_key"),
            )
            if getattr(self.win, "statusBar", None):
                self.win.statusBar.showMessage(str(exc), 5000)
            return False

        updated_entry = build_datamosh_history_entry(
            entry.get("preset_key"),
            output_path,
            entry.get("source_title"),
            amount_key=entry.get("amount_key"),
            generated_clip_id=generated_clip_id,
            file_id=file_obj.id,
            track_number=track_number,
            position=source_position,
        )
        self._remember_history_entry(source_clip_id, updated_entry)

        if restored:
            message = get_app()._tr("Restored cached %(preset)s clip above the source.") % {
                "preset": entry.get("preset_label") or "datamosh"
            }
        else:
            message = get_app()._tr("Selected cached %(preset)s clip.") % {
                "preset": entry.get("preset_label") or "datamosh"
            }
        self._set_state(
            source_clip_id,
            "history",
            message,
            preset_key=entry.get("preset_key"),
        )
        if getattr(self.win, "statusBar", None):
            self.win.statusBar.showMessage(message, 5000)
        return True

    def _on_job_finished(self, clip_id, status, payload):
        clip_id = str(clip_id or "")
        with self._lock:
            self._jobs.pop(clip_id, None)

        if status == "failed":
            error_text = str((payload or {}).get("error") or get_app()._tr("Datamosh generation failed."))
            self._set_state(clip_id, "error", error_text)
            if getattr(self.win, "statusBar", None):
                self.win.statusBar.showMessage(error_text, 5000)
            return

        clip = Clip.get(id=clip_id)
        if not clip:
            self._set_state(
                clip_id,
                "ready",
                get_app()._tr("Datamosh asset is ready in the cache."),
                preset_key=(payload or {}).get("preset_key"),
            )
            return

        preset_key = (payload or {}).get("preset_key")
        amount_key = normalize_datamosh_amount_key((payload or {}).get("amount_key"))
        variant_label = format_datamosh_variant_label(preset_key, amount_key)
        source_title = str((payload or {}).get("source_title") or clip.title() or "Clip")
        display_name = "{} - {}".format(source_title, variant_label)
        output_path = (payload or {}).get("output_path")

        try:
            file_obj = self._import_output_file(output_path, display_name)
            source_position = _safe_float(clip.data.get("position", 0.0))
            target_track_number = self._nearest_available_track_above(clip.data)
            existing_generated = self._find_existing_generated_clip(file_obj.id, source_position, target_track_number)
            if existing_generated:
                generated_clip_id = existing_generated.id
            else:
                new_clip = self.win.timeline.addClip(
                    file_obj.id,
                    QPointF(source_position, 0.0),
                    target_track_number,
                    ignore_refresh=False,
                    call_manual_move=False,
                )
                generated_clip_id = new_clip.get("id") if isinstance(new_clip, dict) else ""
            self._select_clip(generated_clip_id)
            self._remember_history_entry(
                clip_id,
                build_datamosh_history_entry(
                    preset_key,
                    output_path,
                    source_title,
                    amount_key=amount_key,
                    generated_clip_id=generated_clip_id,
                    file_id=file_obj.id,
                    track_number=target_track_number,
                    position=source_position,
                ),
            )
        except Exception as exc:
            log.warning("Failed to finalize datamosh clip %s: %s", clip_id, exc, exc_info=True)
            self._set_state(
                clip_id,
                "error",
                str(exc or get_app()._tr("Failed to place the generated datamosh clip.")),
                preset_key=preset_key,
            )
            if getattr(self.win, "statusBar", None):
                self.win.statusBar.showMessage(str(exc), 5000)
            return

        if status == "cached":
            message = get_app()._tr("Using cached %(preset)s clip above the source.") % {
                "preset": variant_label or "datamosh"
            }
            final_status = "cached"
        else:
            message = get_app()._tr("Placed %(preset)s clip above the source.") % {
                "preset": variant_label or "datamosh"
            }
            final_status = "ready"
        self._set_state(clip_id, final_status, message, preset_key=preset_key)
        if getattr(self.win, "statusBar", None):
            self.win.statusBar.showMessage(message, 5000)
