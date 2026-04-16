"""
 @file
 @brief Compact clip-level effect card helpers and dock controls
"""

import copy
import json

import openshot
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from classes.app import get_app
from classes.query import Clip
from classes.ui_text import sanitize_ui_text


EFFECT_CARD_ORDER = (
    "punch_zoom",
    "jugg_shake",
    "rgb_split",
    "glitch_ripple",
)
EFFECT_CARD_AMOUNT_DEFAULT_KEY = "default"
EFFECT_CARD_AMOUNT_ORDER = (
    "soft",
    EFFECT_CARD_AMOUNT_DEFAULT_KEY,
    "hard",
)

EFFECT_CARD_PRESETS = {
    "punch_zoom": {
        "label": "Punch Zoom",
        "description": "Quick impact zoom",
    },
    "jugg_shake": {
        "label": "Jugg Shake",
        "description": "Fast handheld shake",
    },
    "rgb_split": {
        "label": "RGB Split",
        "description": "Offset channel punch",
    },
    "glitch_ripple": {
        "label": "Glitch Ripple",
        "description": "Wavy digital smear",
    },
}
EFFECT_CARD_AMOUNT_PRESETS = {
    "soft": {
        "label": "Soft",
        "multiplier": 0.72,
    },
    EFFECT_CARD_AMOUNT_DEFAULT_KEY: {
        "label": "Default",
        "multiplier": 1.0,
    },
    "hard": {
        "label": "Hard",
        "multiplier": 1.35,
    },
}

_BACKUP_KEYS = (
    "gravity",
    "origin_x",
    "origin_y",
    "rotation",
    "scale_x",
    "scale_y",
)
_PRESET_UI_KEY = "effect_card_preset"
_AMOUNT_UI_KEY = "effect_card_amount"
_BACKUP_UI_KEY = "effect_card_backup"
_MANAGED_UI_KEY = "effect_card_managed"
_ROLE_UI_KEY = "effect_card_role"


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


def _item_title(item, fallback="Clip"):
    title_func = getattr(item, "title", None)
    if callable(title_func):
        try:
            title = str(title_func() or "").strip()
        except Exception:
            title = ""
        if title:
            return sanitize_ui_text(title)
    data = _item_data(item)
    if isinstance(data, dict):
        title = str(data.get("title") or "").strip()
        if title:
            return sanitize_ui_text(title)
    return sanitize_ui_text(fallback)


def clip_supports_effect_cards(clip_data):
    """Return True when the clip has a visual source that can use look cards."""
    if not isinstance(clip_data, dict):
        return False
    reader = clip_data.get("reader")
    if not isinstance(reader, dict):
        return False
    return bool(reader.get("has_video") or reader.get("has_single_image"))


def clip_has_managed_effect_card(clip_data):
    """Return True when the clip already contains a managed look-card stack."""
    effects = clip_data.get("effects")
    if not isinstance(effects, list):
        return False
    for effect in effects:
        if not isinstance(effect, dict):
            continue
        ui_data = effect.get("ui")
        if isinstance(ui_data, dict) and ui_data.get(_MANAGED_UI_KEY):
            return True
    return False


def _normalize_effect_card_amount_key(amount_key):
    normalized = str(amount_key or EFFECT_CARD_AMOUNT_DEFAULT_KEY)
    if normalized not in EFFECT_CARD_AMOUNT_PRESETS:
        return EFFECT_CARD_AMOUNT_DEFAULT_KEY
    return normalized


def _effect_card_amount_multiplier(amount_key):
    amount_key = _normalize_effect_card_amount_key(amount_key)
    return float(EFFECT_CARD_AMOUNT_PRESETS[amount_key].get("multiplier", 1.0))


def _scale_amount_value(value, amount_key, neutral=0.0):
    return float(neutral) + ((float(value) - float(neutral)) * _effect_card_amount_multiplier(amount_key))


def _scale_curve_values(values, amount_key, neutral=0.0):
    scaled = []
    for entry in values:
        if len(entry) == 2:
            progress, value = entry
            scaled.append((progress, _scale_amount_value(value, amount_key, neutral)))
        else:
            progress, value, interpolation = entry
            scaled.append((progress, _scale_amount_value(value, amount_key, neutral), interpolation))
    return tuple(scaled)


def get_clip_effect_card_preset_key(clip_data):
    """Return the current managed look-card preset for a clip, if any."""
    if not isinstance(clip_data, dict):
        return None

    ui_data = clip_data.get("ui")
    if isinstance(ui_data, dict):
        preset_key = ui_data.get(_PRESET_UI_KEY)
        if preset_key in EFFECT_CARD_PRESETS:
            return preset_key

    detected = set()
    effects = clip_data.get("effects")
    if isinstance(effects, list):
        for effect in effects:
            if not isinstance(effect, dict):
                continue
            effect_ui = effect.get("ui")
            if not isinstance(effect_ui, dict) or not effect_ui.get(_MANAGED_UI_KEY):
                continue
            preset_key = effect_ui.get(_PRESET_UI_KEY)
            if preset_key in EFFECT_CARD_PRESETS:
                detected.add(preset_key)

    if len(detected) == 1:
        return next(iter(detected))
    return None


def get_clip_effect_card_amount_key(clip_data):
    """Return the current managed look-card amount for a clip, if any."""
    if not isinstance(clip_data, dict):
        return None

    preset_key = get_clip_effect_card_preset_key(clip_data)
    if not preset_key:
        return None

    ui_data = clip_data.get("ui")
    if isinstance(ui_data, dict):
        amount_key = ui_data.get(_AMOUNT_UI_KEY)
        if amount_key in EFFECT_CARD_AMOUNT_PRESETS:
            return amount_key

    detected = set()
    effects = clip_data.get("effects")
    if isinstance(effects, list):
        for effect in effects:
            if not isinstance(effect, dict):
                continue
            effect_ui = effect.get("ui")
            if not isinstance(effect_ui, dict) or not effect_ui.get(_MANAGED_UI_KEY):
                continue
            amount_key = effect_ui.get(_AMOUNT_UI_KEY)
            if amount_key in EFFECT_CARD_AMOUNT_PRESETS:
                detected.add(amount_key)

    if len(detected) == 1:
        return next(iter(detected))
    return EFFECT_CARD_AMOUNT_DEFAULT_KEY


def resolve_effect_card_target(selection, clip_lookup=None, tr=None):
    """Resolve selected visual clips for the compact clip look dock."""
    tr = tr or (lambda text: text)
    clip_lookup = clip_lookup or (lambda clip_id: Clip.get(id=clip_id))

    selection = [sel for sel in (selection or []) if isinstance(sel, dict)]
    clip_ids = [sel.get("id") for sel in selection if sel.get("type") == "clip" and sel.get("id")]
    if not clip_ids:
        return {
            "enabled": False,
            "clip_ids": [],
            "message": tr("Select one or more visual clips to apply a one-click look."),
        }

    visual_ids = []
    titles = []
    preset_keys = []
    amount_keys = []
    has_managed_style = False
    for clip_id in clip_ids:
        clip = clip_lookup(clip_id)
        clip_data = _item_data(clip)
        if not clip_data or not clip_supports_effect_cards(clip_data):
            continue
        visual_ids.append(clip_id)
        titles.append(_item_title(clip))
        preset_key = get_clip_effect_card_preset_key(clip_data)
        preset_keys.append(preset_key)
        amount_keys.append(get_clip_effect_card_amount_key(clip_data))
        has_managed_style = has_managed_style or bool(preset_key) or clip_has_managed_effect_card(clip_data)

    if not visual_ids:
        return {
            "enabled": False,
            "clip_ids": [],
            "message": tr("These cards only work on clips with a visible image or video."),
        }

    current_preset_key = None
    current_amount_key = None
    if preset_keys and all(key == preset_keys[0] for key in preset_keys) and preset_keys[0] in EFFECT_CARD_PRESETS:
        current_preset_key = preset_keys[0]
    if amount_keys and any(key is not None for key in amount_keys) and all(key == amount_keys[0] for key in amount_keys):
        current_amount_key = _normalize_effect_card_amount_key(amount_keys[0])

    if len(visual_ids) == 1:
        summary = tr("Selected clip - %(title)s") % {"title": titles[0] or tr("Clip")}
    else:
        summary = tr("%(count)d selected clips") % {"count": len(visual_ids)}

    if current_preset_key:
        summary = f"{summary} - {tr(EFFECT_CARD_PRESETS[current_preset_key]['label'])}"
        message = tr("Pick another card to swap the look, or clear it.")
    elif has_managed_style:
        message = tr("Selected clips have mixed looks. Pick one card to normalize them.")
    else:
        message = tr("Pick a card to apply a quick shake, zoom, or color hit.")

    return {
        "enabled": True,
        "clip_ids": visual_ids,
        "summary": summary,
        "message": message,
        "current_preset_key": current_preset_key,
        "current_amount_key": current_amount_key,
        "has_managed_style": has_managed_style,
    }


def _ensure_clip_ui(clip_data):
    ui_data = clip_data.get("ui")
    if not isinstance(ui_data, dict):
        ui_data = {}
        clip_data["ui"] = ui_data
    return ui_data


def _cleanup_clip_ui(clip_data):
    ui_data = clip_data.get("ui")
    if isinstance(ui_data, dict) and not ui_data:
        clip_data.pop("ui", None)


def _capture_effect_card_backup(clip_data):
    ui_data = _ensure_clip_ui(clip_data)
    if isinstance(ui_data.get(_BACKUP_UI_KEY), dict):
        return False

    values = {}
    missing = []
    for key in _BACKUP_KEYS:
        if key in clip_data:
            values[key] = copy.deepcopy(clip_data[key])
        else:
            missing.append(key)

    ui_data[_BACKUP_UI_KEY] = {"values": values, "missing": missing}
    return True


def _restore_effect_card_backup(clip_data, drop_backup=True):
    ui_data = clip_data.get("ui")
    backup = ui_data.get(_BACKUP_UI_KEY) if isinstance(ui_data, dict) else None
    if not isinstance(backup, dict):
        return False

    values = backup.get("values") if isinstance(backup.get("values"), dict) else {}
    missing = set(backup.get("missing") or [])
    changed = False

    for key in _BACKUP_KEYS:
        if key in values:
            restored = copy.deepcopy(values[key])
            if clip_data.get(key) != restored:
                clip_data[key] = restored
                changed = True
        elif key in missing and key in clip_data:
            clip_data.pop(key, None)
            changed = True

    if drop_backup and isinstance(ui_data, dict) and _BACKUP_UI_KEY in ui_data:
        ui_data.pop(_BACKUP_UI_KEY, None)
        changed = True
        _cleanup_clip_ui(clip_data)

    return changed


def _remove_managed_effects(clip_data):
    effects = clip_data.get("effects")
    if not isinstance(effects, list):
        return False

    filtered_effects = []
    removed = False
    for effect in effects:
        if not isinstance(effect, dict):
            filtered_effects.append(effect)
            continue
        ui_data = effect.get("ui")
        if isinstance(ui_data, dict) and ui_data.get(_MANAGED_UI_KEY):
            removed = True
            continue
        filtered_effects.append(effect)

    if not removed:
        return False

    clip_data["effects"] = filtered_effects
    return True


def _frame_bounds_for_clip(clip_data, fps_float):
    start_s = _safe_float(clip_data.get("start", 0.0))
    end_s = _safe_float(clip_data.get("end", start_s), start_s)
    if end_s <= start_s:
        end_s = start_s + max(1.0 / max(fps_float, 1.0), _safe_float(clip_data.get("duration", 0.0), 0.0))

    start_frame = max(1, int(round(start_s * fps_float)) + 1)
    end_frame = max(start_frame + 1, int(round(end_s * fps_float)) + 1)
    return start_frame, end_frame


def _frame_at_progress(start_frame, end_frame, progress):
    clamped = min(max(float(progress), 0.0), 1.0)
    return int(round(start_frame + ((end_frame - start_frame) * clamped)))


def _make_point(frame, value, interpolation):
    point = openshot.Point(int(frame), float(value), int(interpolation))
    return json.loads(point.Json())


def _build_curve_points(start_frame, end_frame, values, default_interpolation):
    points_by_frame = {}
    for entry in values:
        if len(entry) == 2:
            progress, value = entry
            interpolation = default_interpolation
        else:
            progress, value, interpolation = entry
        frame = _frame_at_progress(start_frame, end_frame, progress)
        points_by_frame[frame] = _make_point(frame, value, interpolation)
    return [points_by_frame[frame] for frame in sorted(points_by_frame)]


def _set_points(target, key, points):
    target[key] = {"Points": [copy.deepcopy(point) for point in points]}


def _next_effect_order(effects):
    max_order = -1
    for index, effect in enumerate(effects):
        if not isinstance(effect, dict):
            continue
        try:
            max_order = max(max_order, int(effect.get("order", index)))
        except (TypeError, ValueError):
            max_order = max(max_order, index)
    return max_order + 1


def _create_managed_effect(effect_name, preset_key, amount_key, role, generate_id_func, order):
    effect = openshot.EffectInfo().CreateEffect(effect_name)
    effect.Id(generate_id_func())
    effect_data = json.loads(effect.Json())
    effect_data["order"] = int(order)
    ui_data = effect_data.get("ui")
    if not isinstance(ui_data, dict):
        ui_data = {}
        effect_data["ui"] = ui_data
    ui_data[_MANAGED_UI_KEY] = True
    ui_data[_PRESET_UI_KEY] = preset_key
    ui_data[_AMOUNT_UI_KEY] = _normalize_effect_card_amount_key(amount_key)
    ui_data[_ROLE_UI_KEY] = role
    return effect_data


def _apply_punch_zoom_preset(clip_data, fps_float, amount_key, generate_id_func, starting_order):
    start_frame, end_frame = _frame_bounds_for_clip(clip_data, fps_float)

    clip_data["gravity"] = int(getattr(openshot, "GRAVITY_CENTER", 0))
    scale_points = _build_curve_points(
        start_frame,
        end_frame,
        _scale_curve_values(
            (
            (0.00, 1.18, getattr(openshot, "BEZIER", 0)),
            (0.12, 1.10, getattr(openshot, "BEZIER", 0)),
            (0.28, 1.04, getattr(openshot, "BEZIER", 0)),
            (1.00, 1.03, getattr(openshot, "LINEAR", 1)),
            ),
            amount_key,
            neutral=1.0,
        ),
        getattr(openshot, "BEZIER", 0),
    )
    rotation_points = _build_curve_points(
        start_frame,
        end_frame,
        _scale_curve_values(
            (
            (0.00, -0.6, getattr(openshot, "BEZIER", 0)),
            (0.10, 0.35, getattr(openshot, "BEZIER", 0)),
            (0.22, 0.05, getattr(openshot, "BEZIER", 0)),
            (0.35, 0.00, getattr(openshot, "LINEAR", 1)),
            (1.00, 0.00, getattr(openshot, "LINEAR", 1)),
            ),
            amount_key,
        ),
        getattr(openshot, "BEZIER", 0),
    )
    _set_points(clip_data, "scale_x", scale_points)
    _set_points(clip_data, "scale_y", scale_points)
    _set_points(clip_data, "rotation", rotation_points)

    blur = _create_managed_effect("Blur", "punch_zoom", amount_key, "blur", generate_id_func, starting_order)
    blur_points = _build_curve_points(
        start_frame,
        end_frame,
        _scale_curve_values(
            (
            (0.00, 18.0, getattr(openshot, "LINEAR", 1)),
            (0.10, 8.0, getattr(openshot, "LINEAR", 1)),
            (0.24, 0.0, getattr(openshot, "LINEAR", 1)),
            (1.00, 0.0, getattr(openshot, "LINEAR", 1)),
            ),
            amount_key,
        ),
        getattr(openshot, "LINEAR", 1),
    )
    _set_points(blur, "horizontal_radius", blur_points)
    _set_points(blur, "vertical_radius", blur_points)
    _set_points(
        blur,
        "sigma",
        _build_curve_points(
            start_frame,
            end_frame,
            _scale_curve_values(((0.00, 7.0), (0.10, 3.0), (0.24, 0.0), (1.00, 0.0)), amount_key),
            getattr(openshot, "LINEAR", 1),
        ),
    )

    brightness = _create_managed_effect(
        "Brightness",
        "punch_zoom",
        amount_key,
        "brightness",
        generate_id_func,
        starting_order + 1,
    )
    _set_points(
        brightness,
        "brightness",
        _build_curve_points(
            start_frame,
            end_frame,
            _scale_curve_values(((0.00, 0.08), (0.12, 0.03), (0.24, 0.0), (1.00, 0.0)), amount_key),
            getattr(openshot, "LINEAR", 1),
        ),
    )
    _set_points(
        brightness,
        "contrast",
        _build_curve_points(
            start_frame,
            end_frame,
            _scale_curve_values(((0.00, 6.5), (0.24, 4.0), (1.00, 3.2)), amount_key, neutral=3.0),
            getattr(openshot, "LINEAR", 1),
        ),
    )
    return [blur, brightness]


def _apply_jugg_shake_preset(clip_data, fps_float, amount_key, generate_id_func, starting_order):
    start_frame, end_frame = _frame_bounds_for_clip(clip_data, fps_float)

    shift = _create_managed_effect("Shift", "jugg_shake", amount_key, "shake", generate_id_func, starting_order)
    _set_points(
        shift,
        "x",
        _build_curve_points(
            start_frame,
            end_frame,
            _scale_curve_values(
                (
                (0.00, 0.000),
                (0.06, -0.055),
                (0.12, 0.040),
                (0.18, -0.030),
                (0.26, 0.020),
                (0.34, -0.012),
                (0.52, 0.006),
                (1.00, 0.000),
                ),
                amount_key,
            ),
            getattr(openshot, "LINEAR", 1),
        ),
    )
    _set_points(
        shift,
        "y",
        _build_curve_points(
            start_frame,
            end_frame,
            _scale_curve_values(
                (
                (0.00, 0.000),
                (0.06, 0.034),
                (0.12, -0.022),
                (0.18, 0.016),
                (0.26, -0.010),
                (0.34, 0.008),
                (0.52, -0.004),
                (1.00, 0.000),
                ),
                amount_key,
            ),
            getattr(openshot, "LINEAR", 1),
        ),
    )

    blur = _create_managed_effect("Blur", "jugg_shake", amount_key, "blur", generate_id_func, starting_order + 1)
    _set_points(
        blur,
        "horizontal_radius",
        _build_curve_points(
            start_frame,
            end_frame,
            _scale_curve_values(((0.00, 8.0), (0.20, 3.0), (0.40, 1.0), (1.00, 0.0)), amount_key),
            getattr(openshot, "LINEAR", 1),
        ),
    )
    _set_points(
        blur,
        "vertical_radius",
        _build_curve_points(
            start_frame,
            end_frame,
            _scale_curve_values(((0.00, 5.0), (0.20, 2.0), (0.40, 1.0), (1.00, 0.0)), amount_key),
            getattr(openshot, "LINEAR", 1),
        ),
    )
    _set_points(
        blur,
        "sigma",
        _build_curve_points(
            start_frame,
            end_frame,
            _scale_curve_values(((0.00, 3.0), (0.20, 1.5), (1.00, 0.0)), amount_key),
            getattr(openshot, "LINEAR", 1),
        ),
    )
    return [shift, blur]


def _apply_rgb_split_preset(clip_data, fps_float, amount_key, generate_id_func, starting_order):
    start_frame, end_frame = _frame_bounds_for_clip(clip_data, fps_float)

    color_shift = _create_managed_effect(
        "ColorShift",
        "rgb_split",
        amount_key,
        "color_shift",
        generate_id_func,
        starting_order,
    )
    for channel, values in (
        ("red_x", ((0.00, 0.030), (0.18, 0.014), (1.00, 0.008))),
        ("green_x", ((0.00, 0.000), (1.00, 0.000))),
        ("blue_x", ((0.00, -0.032), (0.18, -0.014), (1.00, -0.008))),
        ("red_y", ((0.00, 0.008), (1.00, 0.000))),
        ("green_y", ((0.00, 0.000), (1.00, 0.000))),
        ("blue_y", ((0.00, -0.008), (1.00, 0.000))),
        ("alpha_x", ((0.00, 0.000), (1.00, 0.000))),
        ("alpha_y", ((0.00, 0.000), (1.00, 0.000))),
    ):
        _set_points(
            color_shift,
            channel,
            _build_curve_points(
                start_frame,
                end_frame,
                _scale_curve_values(values, amount_key),
                getattr(openshot, "LINEAR", 1),
            ),
        )

    saturation = _create_managed_effect(
        "Saturation",
        "rgb_split",
        amount_key,
        "saturation",
        generate_id_func,
        starting_order + 1,
    )
    sat_points = _build_curve_points(
        start_frame,
        end_frame,
        _scale_curve_values(((0.00, 1.25), (0.20, 1.18), (1.00, 1.12)), amount_key, neutral=1.0),
        getattr(openshot, "LINEAR", 1),
    )
    for key in ("saturation", "saturation_R", "saturation_G", "saturation_B"):
        _set_points(saturation, key, sat_points)

    return [color_shift, saturation]


def _apply_glitch_ripple_preset(clip_data, fps_float, amount_key, generate_id_func, starting_order):
    start_frame, end_frame = _frame_bounds_for_clip(clip_data, fps_float)

    wave = _create_managed_effect("Wave", "glitch_ripple", amount_key, "wave", generate_id_func, starting_order)
    for key, values in (
        ("amplitude", ((0.00, 0.72), (0.18, 0.34), (1.00, 0.18))),
        ("multiplier", ((0.00, 0.48), (0.30, 0.26), (1.00, 0.20))),
        ("shift_x", ((0.00, 0.030), (0.22, 0.010), (1.00, 0.000))),
        ("speed_y", ((0.00, 0.55), (1.00, 0.20))),
        ("wavelength", ((0.00, 0.09), (1.00, 0.16))),
    ):
        _set_points(
            wave,
            key,
            _build_curve_points(
                start_frame,
                end_frame,
                values if key == "wavelength" else _scale_curve_values(values, amount_key),
                getattr(openshot, "LINEAR", 1),
            ),
        )

    color_shift = _create_managed_effect(
        "ColorShift",
        "glitch_ripple",
        amount_key,
        "color_shift",
        generate_id_func,
        starting_order + 1,
    )
    for channel, values in (
        ("red_x", ((0.00, 0.018), (1.00, 0.006))),
        ("green_x", ((0.00, 0.000), (1.00, 0.000))),
        ("blue_x", ((0.00, -0.018), (1.00, -0.006))),
        ("red_y", ((0.00, 0.004), (1.00, 0.000))),
        ("green_y", ((0.00, 0.000), (1.00, 0.000))),
        ("blue_y", ((0.00, -0.004), (1.00, 0.000))),
        ("alpha_x", ((0.00, 0.000), (1.00, 0.000))),
        ("alpha_y", ((0.00, 0.000), (1.00, 0.000))),
    ):
        _set_points(
            color_shift,
            channel,
            _build_curve_points(
                start_frame,
                end_frame,
                _scale_curve_values(values, amount_key),
                getattr(openshot, "LINEAR", 1),
            ),
        )

    return [wave, color_shift]


def clear_clip_effect_card_preset(clip_data):
    """Remove the managed look-card stack and restore any backed-up transforms."""
    if not isinstance(clip_data, dict):
        return False

    changed = _remove_managed_effects(clip_data)
    changed = _restore_effect_card_backup(clip_data, drop_backup=True) or changed

    ui_data = clip_data.get("ui")
    if isinstance(ui_data, dict) and _PRESET_UI_KEY in ui_data:
        ui_data.pop(_PRESET_UI_KEY, None)
        ui_data.pop(_AMOUNT_UI_KEY, None)
        changed = True
        _cleanup_clip_ui(clip_data)

    return changed


def apply_clip_effect_card_preset(clip_data, fps_float, preset_key, generate_id_func, amount_key=EFFECT_CARD_AMOUNT_DEFAULT_KEY):
    """Apply or replace a managed look-card preset on one clip."""
    if not isinstance(clip_data, dict) or preset_key not in EFFECT_CARD_PRESETS:
        return False
    if not callable(generate_id_func):
        return False
    amount_key = _normalize_effect_card_amount_key(amount_key)

    changed = _capture_effect_card_backup(clip_data)
    changed = _remove_managed_effects(clip_data) or changed
    changed = _restore_effect_card_backup(clip_data, drop_backup=False) or changed

    ui_data = _ensure_clip_ui(clip_data)
    if ui_data.get(_PRESET_UI_KEY) != preset_key:
        ui_data[_PRESET_UI_KEY] = preset_key
        changed = True
    if ui_data.get(_AMOUNT_UI_KEY) != amount_key:
        ui_data[_AMOUNT_UI_KEY] = amount_key
        changed = True

    effects = clip_data.get("effects")
    if not isinstance(effects, list):
        effects = list(effects) if effects else []
        clip_data["effects"] = effects
        changed = True

    order = _next_effect_order(effects)
    if preset_key == "punch_zoom":
        managed_effects = _apply_punch_zoom_preset(clip_data, fps_float, amount_key, generate_id_func, order)
    elif preset_key == "jugg_shake":
        managed_effects = _apply_jugg_shake_preset(clip_data, fps_float, amount_key, generate_id_func, order)
    elif preset_key == "rgb_split":
        managed_effects = _apply_rgb_split_preset(clip_data, fps_float, amount_key, generate_id_func, order)
    elif preset_key == "glitch_ripple":
        managed_effects = _apply_glitch_ripple_preset(clip_data, fps_float, amount_key, generate_id_func, order)
    else:
        return changed

    effects.extend(managed_effects)
    return True


class EffectCardDockPanel(QFrame):
    """Small one-click clip-look controls for selected visual clips."""

    def __init__(self, parent=None):
        super().__init__(parent)
        tr = getattr(get_app(), "_tr", lambda text: text)

        self._selection = []
        self._clip_ids = []
        self._target = None
        self._amount_key = EFFECT_CARD_AMOUNT_DEFAULT_KEY
        self.setObjectName("effectCardDockPanel")
        self.setFrameShape(QFrame.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        header = QLabel(f"<strong>{tr('Clip Looks')}</strong>", self)
        header.setTextFormat(header.textFormat())
        root.addWidget(header)

        self.summary_label = QLabel(tr("Select one or more visual clips to apply a one-click look."), self)
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.status_label = QLabel(tr("These cards keep the interface simple by applying a managed preset stack."), self)
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self._preset_buttons = {}
        for index, preset_key in enumerate(EFFECT_CARD_ORDER):
            preset = EFFECT_CARD_PRESETS[preset_key]
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

        amount_label = QLabel(f"<strong>{tr('Amount')}</strong>", self)
        amount_label.setTextFormat(amount_label.textFormat())
        root.addWidget(amount_label)

        amount_grid = QGridLayout()
        amount_grid.setContentsMargins(0, 0, 0, 0)
        amount_grid.setHorizontalSpacing(6)
        amount_grid.setVerticalSpacing(6)
        self._amount_buttons = {}
        for index, amount_key in enumerate(EFFECT_CARD_AMOUNT_ORDER):
            amount = EFFECT_CARD_AMOUNT_PRESETS[amount_key]
            button = QPushButton(tr(amount["label"]), self)
            button.setCheckable(True)
            button.setMinimumHeight(30)
            button.clicked.connect(lambda _checked=False, key=amount_key: self._select_amount(key))
            amount_grid.addWidget(button, 0, index)
            self._amount_buttons[amount_key] = button
        root.addLayout(amount_grid)

        self.clear_button = QPushButton(tr("Clear Style"), self)
        self.clear_button.clicked.connect(self._clear_preset)
        root.addWidget(self.clear_button)

        self.note_label = QLabel(
            tr("Use cards for the fast path. You can still fine-tune individual properties afterward."),
            self,
        )
        self.note_label.setWordWrap(True)
        root.addWidget(self.note_label)

        window = getattr(get_app(), "window", None)
        if window and getattr(window, "propertyTableView", None):
            window.propertyTableView.loadProperties.connect(self.update_selection)

        self._set_controls_enabled(False)
        self.hide()

    def _set_controls_enabled(self, enabled):
        for child in self.findChildren(QWidget):
            if child in (self.summary_label, self.status_label, self.note_label):
                continue
            child.setEnabled(enabled)

    def _sync_amount_buttons(self):
        for amount_key, button in self._amount_buttons.items():
            button.setChecked(amount_key == self._amount_key)

    def _select_amount(self, amount_key):
        self._amount_key = _normalize_effect_card_amount_key(amount_key)
        self._sync_amount_buttons()
        if not self._target or not self._target.get("enabled"):
            return
        current_preset_key = self._target.get("current_preset_key")
        if current_preset_key in EFFECT_CARD_PRESETS and self._clip_ids:
            self._apply_preset(current_preset_key)

    def refresh_from_current_selection(self):
        window = getattr(get_app(), "window", None)
        selection = list(getattr(window, "selected_items", []) or []) if window else []
        self.update_selection(selection)

    def update_selection(self, selection):
        self._selection = list(selection or [])
        has_clip = any(isinstance(sel, dict) and sel.get("type") == "clip" for sel in self._selection)
        if not has_clip:
            self._clip_ids = []
            self._target = None
            self.summary_label.setText(
                sanitize_ui_text(get_app()._tr("Select one or more visual clips to apply a one-click look."))
            )
            self.status_label.setText(
                sanitize_ui_text(
                    get_app()._tr("These cards keep the interface simple by applying a managed preset stack.")
                )
            )
            self._set_controls_enabled(False)
            self.hide()
            return

        target = resolve_effect_card_target(self._selection, tr=get_app()._tr)
        self._target = target
        self._clip_ids = list(target.get("clip_ids") or [])
        if target.get("current_amount_key") in EFFECT_CARD_AMOUNT_PRESETS:
            self._amount_key = target["current_amount_key"]
        self.show()
        self.summary_label.setText(
            sanitize_ui_text(str(target.get("summary") or get_app()._tr("Clip Looks")))
        )
        self.status_label.setText(
            sanitize_ui_text(str(target.get("message") or get_app()._tr("Pick a card to apply a one-click look.")))
        )
        self._set_controls_enabled(bool(target.get("enabled")))
        self._sync_amount_buttons()
        self.clear_button.setEnabled(bool(target.get("enabled")) and bool(target.get("has_managed_style")))

    def _apply_preset(self, preset_key):
        if not self._clip_ids:
            return
        timeline = getattr(get_app().window, "timeline", None)
        if not timeline:
            return
        timeline.Apply_Effect_Card_Preset(self._clip_ids, preset_key, amount_key=self._amount_key)
        self.refresh_from_current_selection()

    def _clear_preset(self):
        if not self._clip_ids:
            return
        timeline = getattr(get_app().window, "timeline", None)
        if not timeline:
            return
        timeline.Clear_Effect_Card_Preset(self._clip_ids)
        self.refresh_from_current_selection()
