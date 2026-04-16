"""
 @file
 @brief Lightweight preview-performance helpers for heavy edit selections
"""


PREVIEW_PERFORMANCE_MODE_DEFAULT = "quality"
PREVIEW_PERFORMANCE_MODES = {
    "quality": {
        "label": "Full Preview",
        "scale": 1.0,
    },
    "draft": {
        "label": "Draft Preview",
        "scale": 0.6,
    },
}
_HEAVY_UI_KEYS = {
    "effect_card_preset",
    "datamosh_source_clip_id",
    "datamosh_preset_key",
}
_PROXY_ACTIVE_STATES = {"queued", "running", "canceling"}


def _dedupe_ids(values):
    seen = set()
    ordered = []
    for value in values or []:
        text = str(value or "")
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def normalize_preview_performance_mode(mode):
    normalized = str(mode or PREVIEW_PERFORMANCE_MODE_DEFAULT)
    if normalized not in PREVIEW_PERFORMANCE_MODES:
        return PREVIEW_PERFORMANCE_MODE_DEFAULT
    return normalized


def preview_performance_scale_factor(mode):
    mode = normalize_preview_performance_mode(mode)
    return float(PREVIEW_PERFORMANCE_MODES[mode].get("scale", 1.0))


def preview_toggle_action_label(mode):
    mode = normalize_preview_performance_mode(mode)
    if mode == "draft":
        return PREVIEW_PERFORMANCE_MODES["quality"]["label"]
    return PREVIEW_PERFORMANCE_MODES["draft"]["label"]


def preview_toggle_action_description(mode):
    mode = normalize_preview_performance_mode(mode)
    if mode == "draft":
        return "Restore full-resolution preview rendering."
    return "Lower preview resolution for smoother playback."


def clip_preview_file_id(clip_data):
    if not isinstance(clip_data, dict):
        return ""
    reader = clip_data.get("reader") if isinstance(clip_data.get("reader"), dict) else {}
    return str(clip_data.get("file_id") or reader.get("id") or "")


def collect_preview_file_ids(clip_payloads):
    seen = set()
    ordered = []
    for clip_data in clip_payloads or []:
        file_id = clip_preview_file_id(clip_data)
        if not file_id or file_id in seen:
            continue
        seen.add(file_id)
        ordered.append(file_id)
    return ordered


def clip_has_nontrivial_time_map(clip_data):
    if not isinstance(clip_data, dict):
        return False
    time_data = clip_data.get("time")
    if not isinstance(time_data, dict):
        return False
    points = time_data.get("Points")
    if not isinstance(points, list) or not points:
        return False
    if len(points) != 1:
        return True
    point = points[0] if isinstance(points[0], dict) else {}
    co = point.get("co") if isinstance(point.get("co"), dict) else {}
    return abs(_safe_float(co.get("X", 1.0), 1.0) - 1.0) > 0.001 or abs(_safe_float(co.get("Y", 1.0), 1.0) - 1.0) > 0.001


def clip_is_heavy_for_preview(clip_data):
    if not isinstance(clip_data, dict):
        return False
    effects = clip_data.get("effects")
    if isinstance(effects, list) and len(effects) > 0:
        return True
    if clip_has_nontrivial_time_map(clip_data):
        return True
    ui_data = clip_data.get("ui")
    if isinstance(ui_data, dict):
        if any(ui_data.get(key) for key in _HEAVY_UI_KEYS):
            return True
    return False


def build_preview_assist_state(
    clip_payloads,
    *,
    context="clip",
    preview_mode=PREVIEW_PERFORMANCE_MODE_DEFAULT,
    has_proxy_reader_lookup=None,
):
    """Return whether preview helpers should be surfaced for the current selection."""
    clip_payloads = [clip for clip in (clip_payloads or []) if isinstance(clip, dict)]
    preview_mode = normalize_preview_performance_mode(preview_mode)
    file_ids = collect_preview_file_ids(clip_payloads)
    heavy_selection = bool(context == "transition" or len(clip_payloads) > 1 or any(clip_is_heavy_for_preview(clip) for clip in clip_payloads))
    if not heavy_selection:
        return {
            "needs_help": False,
            "preview_mode": preview_mode,
            "file_ids": file_ids,
            "toggle_label": preview_toggle_action_label(preview_mode),
            "toggle_description": preview_toggle_action_description(preview_mode),
            "can_optimize": False,
            "proxy_ready": False,
        }

    proxy_ready = False
    if callable(has_proxy_reader_lookup) and file_ids:
        proxy_ready = all(bool(has_proxy_reader_lookup(file_id)) for file_id in file_ids)

    return {
        "needs_help": True,
        "preview_mode": preview_mode,
        "file_ids": file_ids,
        "toggle_label": preview_toggle_action_label(preview_mode),
        "toggle_description": preview_toggle_action_description(preview_mode),
        "can_optimize": bool(file_ids) and not proxy_ready,
        "proxy_ready": bool(file_ids) and proxy_ready,
    }


def build_proxy_status_state(
    file_ids,
    *,
    preview_mode=PREVIEW_PERFORMANCE_MODE_DEFAULT,
    proxy_state_lookup=None,
    proxy_badge_lookup=None,
):
    """Return a compact proxy/cache strip model for the current selection."""
    file_ids = _dedupe_ids(file_ids)
    preview_mode = normalize_preview_performance_mode(preview_mode)
    mode_label = PREVIEW_PERFORMANCE_MODES[preview_mode]["label"]

    if not file_ids:
        return {
            "visible": False,
            "file_ids": [],
            "headline": "",
            "detail": "",
            "actions": [],
        }

    entries = []
    for file_id in file_ids:
        state = "none"
        if callable(proxy_state_lookup):
            state = str(proxy_state_lookup(file_id) or "none").strip().lower() or "none"
        if state not in {"none", "ready", "missing", "queued", "running", "canceling"}:
            state = "none"
        badge = proxy_badge_lookup(file_id) if callable(proxy_badge_lookup) else None
        entries.append({"file_id": file_id, "state": state, "badge": badge if isinstance(badge, dict) else None})

    total = len(entries)
    ready_count = sum(1 for entry in entries if entry["state"] == "ready")
    missing_count = sum(1 for entry in entries if entry["state"] == "missing")
    active_entries = [entry for entry in entries if entry["state"] in _PROXY_ACTIVE_STATES]
    none_count = total - ready_count - missing_count - len(active_entries)

    clear_action = {
        "key": "preview_cache_clear",
        "label": "Clear Cache",
        "description": "Reset cached preview frames for the current timeline.",
    }

    if active_entries:
        active_label = ""
        if len(active_entries) == 1:
            badge = active_entries[0].get("badge") or {}
            active_label = str(badge.get("label") or active_entries[0]["state"].capitalize())
        else:
            active_label = "{} preview jobs active".format(len(active_entries))
        return {
            "visible": True,
            "file_ids": file_ids,
            "headline": "{} - {}".format(mode_label, active_label),
            "detail": "Optimized preview media is being prepared for smoother playback.",
            "actions": [
                {
                    "key": "preview_proxy_cancel",
                    "label": "Cancel Build",
                    "description": "Stop optimized preview generation for the current selection.",
                },
                clear_action,
            ],
        }

    if ready_count == total:
        headline = "{} - Optimized Preview Ready".format(mode_label)
        detail = "Using lighter source files for smoother playback."
        build_label = "Rebuild Preview"
    elif missing_count == total:
        headline = "{} - Optimized Preview Missing".format(mode_label)
        detail = "The linked preview file is missing. Rebuild or remove the link."
        build_label = "Rebuild Preview"
    elif ready_count or missing_count:
        headline = "{} - Mixed Preview State".format(mode_label)
        detail_parts = []
        if ready_count:
            detail_parts.append("{} ready".format(ready_count))
        if missing_count:
            detail_parts.append("{} missing".format(missing_count))
        if none_count:
            detail_parts.append("{} source".format(none_count))
        detail = " / ".join(detail_parts) or "Preview media varies across this selection."
        build_label = "Rebuild Preview"
    else:
        headline = "{} - Using Source Media".format(mode_label)
        detail = "No optimized preview is linked yet."
        build_label = "Build Preview"

    actions = [
        {
            "key": "preview_proxy_rebuild",
            "label": build_label,
            "description": (
                "Create lighter source files for smoother playback."
                if build_label == "Build Preview"
                else "Regenerate lighter source files for the selected media."
            ),
        },
    ]
    if ready_count or missing_count:
        actions.append(
            {
                "key": "preview_proxy_remove",
                "label": "Remove Preview",
                "description": "Unlink the optimized preview and fall back to the source media.",
            }
        )
    actions.append(clear_action)
    return {
        "visible": True,
        "file_ids": file_ids,
        "headline": headline,
        "detail": detail,
        "actions": actions,
    }
