"""
 @file
 @brief Compact quick-action favorites for the simple editing path
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from classes.app import get_app
from classes.datamosh_service import DATAMOSH_AMOUNT_DEFAULT_KEY, resolve_datamosh_clip_target
from classes.query import Clip, File
from classes.ui_text import sanitize_ui_text
from windows.views.effect_cards import EFFECT_CARD_AMOUNT_DEFAULT_KEY, resolve_effect_card_target
from windows.views.preview_performance import (
    PREVIEW_PERFORMANCE_MODE_DEFAULT,
    build_preview_assist_state,
    build_proxy_status_state,
)
from windows.views.transition_presets import resolve_transition_style_target


QUICK_ACTIONS = {
    "clip_punch_zoom": {
        "label": "Punch Zoom",
        "description": "Add a fast impact zoom",
    },
    "clip_speed_double": {
        "label": "2x Speed",
        "description": "Speed the clip up fast",
    },
    "clip_reverse": {
        "label": "Reverse",
        "description": "Flip the selected clip direction",
    },
    "clip_freeze": {
        "label": "Freeze",
        "description": "Drop a one-second hold at the playhead",
    },
    "clip_jugg_shake": {
        "label": "Jugg Shake",
        "description": "Add a fast handheld shake",
    },
    "clip_cut_mosh": {
        "label": "Cut Mosh",
        "description": "Generate a quick datamosh pass",
    },
    "clip_freeze_hit": {
        "label": "Freeze Hit",
        "description": "Drop a freeze hit at the playhead",
    },
    "preview_toggle_quality": {
        "label": "Draft Preview",
        "description": "Lower preview resolution for smoother playback",
    },
    "preview_optimize": {
        "label": "Optimize Preview",
        "description": "Create lighter source files for smoother playback",
    },
    "transition_jugg_shake": {
        "label": "Jugg Shake",
        "description": "Add a fast shaky handoff",
    },
    "transition_whip_push": {
        "label": "Whip Push",
        "description": "Add a fast directional handoff",
    },
    "transition_find_hit": {
        "label": "Find Hit",
        "description": "Place a marker on the strongest nearby transient",
    },
    "transition_beat_pair": {
        "label": "Beat Pair",
        "description": "Bracket the cut with a one-beat timing window",
    },
}
QUICK_ACTION_ORDER = {
    "clip": (
        "clip_jugg_shake",
        "clip_cut_mosh",
        "clip_speed_double",
        "clip_reverse",
        "clip_freeze",
    ),
    "transition": (
        "transition_jugg_shake",
        "transition_whip_push",
        "transition_find_hit",
        "transition_beat_pair",
    ),
}
FIRST_CUT_ACTION_ORDER = (
    "clip_punch_zoom",
    "clip_jugg_shake",
    "clip_freeze_hit",
    "clip_cut_mosh",
    "clip_speed_double",
    "clip_reverse",
)
QUICK_ACTION_PRIMARY_LIMITS = {
    "clip": 3,
    "transition": 3,
}
FIRST_CUT_MAX_TIMELINE_CLIPS = 2


def _item_data(item):
    if isinstance(item, dict):
        return item
    data = getattr(item, "data", None)
    return data if isinstance(data, dict) else None


def _selected_clip_ids(selection):
    return [
        str(sel.get("id") or "")
        for sel in (selection or [])
        if isinstance(sel, dict) and sel.get("type") == "clip" and sel.get("id")
    ]


def _normalized_project_items(items):
    normalized = []
    for item in items or []:
        data = _item_data(item)
        if isinstance(data, dict):
            normalized.append(data)
    return normalized


def _selection_with_single_clip_fallback(selection, project_clips, project_transitions):
    selection = [sel for sel in (selection or []) if isinstance(sel, dict)]
    if selection:
        return selection, False

    project_clip_entries = _normalized_project_items(project_clips)
    project_transition_entries = _normalized_project_items(project_transitions)
    if len(project_transition_entries) != 0 or len(project_clip_entries) != 1:
        return selection, False

    clip_id = str(project_clip_entries[0].get("id") or "")
    if not clip_id:
        return selection, False
    return [{"id": clip_id, "type": "clip"}], True


def _is_first_cut_context(clip_ids, visual_clip_ids, timeline_clip_count, timeline_transition_count):
    if not clip_ids or not visual_clip_ids:
        return False
    if len(visual_clip_ids) != len(clip_ids):
        return False
    if int(timeline_transition_count or 0) != 0:
        return False
    return 0 < int(timeline_clip_count or 0) <= FIRST_CUT_MAX_TIMELINE_CLIPS


def _clip_title(clip, fallback):
    title_func = getattr(clip, "title", None)
    if callable(title_func):
        try:
            title = str(title_func() or "").strip()
        except Exception:
            title = ""
        if title:
            return sanitize_ui_text(title)
    clip_data = _item_data(clip)
    if isinstance(clip_data, dict):
        title = str(clip_data.get("title") or "").strip()
        if title:
            return sanitize_ui_text(title)
    return sanitize_ui_text(str(fallback or "Clip"))


def build_quick_action_display_state(target, *, show_more=False, tr=None):
    """Return the visible quick-action slice for the current target."""
    tr = tr or (lambda text: text)
    target = target if isinstance(target, dict) else {}
    context = str(target.get("context") or "clip")
    limit = int(QUICK_ACTION_PRIMARY_LIMITS.get(context, 3) or 3)
    actions = [action for action in (target.get("actions") or []) if isinstance(action, dict)]
    enabled_actions = [action for action in actions if bool(action.get("enabled", True))]
    hidden_count = max(0, len(enabled_actions) - limit)

    if show_more or hidden_count <= 0:
        visible_actions = enabled_actions
    else:
        visible_actions = enabled_actions[:limit]

    if hidden_count <= 0:
        toggle_label = ""
    elif show_more:
        toggle_label = tr("Show Fewer")
    else:
        toggle_label = tr("Show %(count)d More") % {"count": hidden_count}

    return {
        "visible_actions": visible_actions,
        "has_overflow": hidden_count > 0,
        "hidden_count": hidden_count,
        "toggle_label": toggle_label,
        "show_more": bool(show_more),
    }


def resolve_quick_action_target(
    selection,
    *,
    clip_lookup=None,
    file_lookup=None,
    datamosh_target_resolver=None,
    effect_target_resolver=None,
    transition_target_resolver=None,
    has_proxy_reader_lookup=None,
    proxy_state_lookup=None,
    proxy_badge_lookup=None,
    preview_mode=PREVIEW_PERFORMANCE_MODE_DEFAULT,
    project_clips=None,
    project_transitions=None,
    tr=None,
):
    """Return the top quick-action context for the current selection."""
    tr = tr or (lambda text: text)
    app = get_app()
    clip_lookup = clip_lookup or (lambda clip_id: Clip.get(id=clip_id))
    file_lookup = file_lookup or (lambda file_id: File.get(id=file_id))
    datamosh_target_resolver = datamosh_target_resolver or resolve_datamosh_clip_target
    effect_target_resolver = effect_target_resolver or resolve_effect_card_target
    transition_target_resolver = transition_target_resolver or resolve_transition_style_target
    has_proxy_reader_lookup = has_proxy_reader_lookup or (
        lambda file_id: bool(getattr(file_lookup(file_id), "data", {}).get("proxy_reader"))
    )
    app_window = getattr(app, "window", None)
    proxy_service = getattr(app_window, "proxy_service", None)
    project = getattr(app, "project", None)
    project_data = getattr(project, "_data", {}) if project else {}
    if not isinstance(project_data, dict):
        project_data = {}
    if project_clips is None:
        project_clips = project_data.get("clips") or []
    if project_transitions is None:
        project_transitions = project_data.get("transitions") or []
    if proxy_state_lookup is None:
        def proxy_state_lookup(file_id):
            if not proxy_service:
                return "none"
            try:
                file_obj = file_lookup(file_id)
            except Exception:
                return "none"
            if not file_obj:
                return "none"
            return proxy_service.get_proxy_state(file_obj)
    if proxy_badge_lookup is None:
        def proxy_badge_lookup(file_id):
            if not proxy_service:
                return None
            return proxy_service.get_file_badge(file_id)

    selection, implicit_selection = _selection_with_single_clip_fallback(
        selection,
        project_clips,
        project_transitions,
    )
    selected_clip_ids = _selected_clip_ids(selection)
    selected_clips = [clip_lookup(clip_id) for clip_id in selected_clip_ids]
    selected_clip_payloads = [_item_data(clip) for clip in selected_clips if _item_data(clip)]
    timeline_clip_count = len(_normalized_project_items(project_clips))
    timeline_transition_count = len(_normalized_project_items(project_transitions))

    try:
        transition_target = transition_target_resolver(selection, clip_lookup=clip_lookup, tr=tr)
    except TypeError:
        transition_target = transition_target_resolver(selection, tr=tr)
    if isinstance(transition_target, dict) and transition_target.get("enabled"):
        preview_assist = build_preview_assist_state(
            selected_clip_payloads,
            context="transition",
            preview_mode=preview_mode,
            has_proxy_reader_lookup=has_proxy_reader_lookup,
        )
        proxy_status = build_proxy_status_state(
            preview_assist.get("file_ids") or [],
            preview_mode=preview_mode,
            proxy_state_lookup=proxy_state_lookup,
            proxy_badge_lookup=proxy_badge_lookup,
        ) if preview_assist.get("needs_help") else {"visible": False, "actions": []}
        actions = [
            {
                "key": action_key,
                "enabled": True,
                "label": tr(QUICK_ACTIONS[action_key]["label"]),
                "description": tr(QUICK_ACTIONS[action_key]["description"]),
            }
            for action_key in QUICK_ACTION_ORDER["transition"]
        ]
        if preview_assist.get("needs_help"):
            actions.extend(
                [
                    {
                        "key": "preview_toggle_quality",
                        "enabled": True,
                        "label": tr(preview_assist["toggle_label"]),
                        "description": tr(preview_assist["toggle_description"]),
                    }
                ]
            )
            if preview_assist.get("can_optimize"):
                actions.append(
                    {
                        "key": "preview_optimize",
                        "enabled": True,
                        "label": tr(QUICK_ACTIONS["preview_optimize"]["label"]),
                        "description": tr(QUICK_ACTIONS["preview_optimize"]["description"]),
                    }
                )
        return {
            "enabled": True,
            "context": "transition",
            "summary": str(transition_target.get("summary") or tr("Quick moves for this handoff")),
            "message": (
                tr("Start here for the quickest handoff changes.")
                if not preview_assist.get("needs_help")
                else tr("Start here for the quickest handoff changes. Draft preview is ready if playback gets heavy.")
            ),
            "actions": actions,
            "transition_target": transition_target,
            "preview_assist": preview_assist,
            "proxy_status": proxy_status,
        }

    clip_ids = selected_clip_ids
    if not clip_ids:
        return {
            "enabled": False,
            "context": "none",
            "summary": tr("Quick Actions"),
            "message": tr("Select a clip or handoff to see quick moves."),
            "actions": [],
        }

    clips = [clip for clip in selected_clips if clip]
    primary_clip_id = clip_ids[0] if len(clip_ids) == 1 else ""
    primary_title = _clip_title(clips[0], tr("Clip")) if clips else tr("Clip")
    effect_target = effect_target_resolver(selection, clip_lookup=clip_lookup, tr=tr)
    datamosh_target = datamosh_target_resolver(selection, clip_lookup=clip_lookup, tr=tr)
    visual_clip_ids = list(effect_target.get("clip_ids") or []) if isinstance(effect_target, dict) else []
    preview_assist = build_preview_assist_state(
        selected_clip_payloads,
        context="clip",
        preview_mode=preview_mode,
        has_proxy_reader_lookup=has_proxy_reader_lookup,
    )
    proxy_status = build_proxy_status_state(
        preview_assist.get("file_ids") or [],
        preview_mode=preview_mode,
        proxy_state_lookup=proxy_state_lookup,
        proxy_badge_lookup=proxy_badge_lookup,
    ) if preview_assist.get("needs_help") else {"visible": False, "actions": []}

    if len(clip_ids) == 1:
        summary = tr("Quick moves - %(title)s") % {"title": primary_title}
    else:
        summary = tr("Quick moves - %(count)d clips") % {"count": len(clip_ids)}

    first_cut_mode = _is_first_cut_context(
        clip_ids,
        visual_clip_ids,
        timeline_clip_count,
        timeline_transition_count,
    )
    if first_cut_mode:
        if len(clip_ids) == 1:
            summary = tr("First cut moves - %(title)s") % {"title": primary_title}
        else:
            summary = tr("First cut moves - %(count)d clips") % {"count": len(clip_ids)}
    elif implicit_selection and len(clip_ids) == 1:
        summary = tr("Start with this clip - %(title)s") % {"title": primary_title}

    if first_cut_mode:
        action_order = FIRST_CUT_ACTION_ORDER + tuple(
            action_key for action_key in QUICK_ACTION_ORDER["clip"]
            if action_key not in FIRST_CUT_ACTION_ORDER
        )
    else:
        action_order = QUICK_ACTION_ORDER["clip"]

    actions = []
    for action_key in action_order:
        enabled = True
        if action_key in ("clip_punch_zoom", "clip_jugg_shake"):
            enabled = bool(visual_clip_ids)
        elif action_key == "clip_cut_mosh":
            enabled = bool(isinstance(datamosh_target, dict) and datamosh_target.get("enabled"))
        actions.append(
            {
                "key": action_key,
                "enabled": enabled,
                "label": tr(QUICK_ACTIONS[action_key]["label"]),
                "description": tr(QUICK_ACTIONS[action_key]["description"]),
            }
        )

    if preview_assist.get("needs_help"):
        actions.append(
            {
                "key": "preview_toggle_quality",
                "enabled": True,
                "label": tr(preview_assist["toggle_label"]),
                "description": tr(preview_assist["toggle_description"]),
            }
        )
        if preview_assist.get("can_optimize"):
            actions.append(
                {
                    "key": "preview_optimize",
                    "enabled": True,
                    "label": tr(QUICK_ACTIONS["preview_optimize"]["label"]),
                    "description": tr(QUICK_ACTIONS["preview_optimize"]["description"]),
                }
            )

    return {
        "enabled": True,
        "context": "clip",
        "summary": summary,
        "message": (
            (
                tr("Your first clip is in. Try one quick move to set the tone.")
                if implicit_selection
                else tr("The first clip is in. Try one quick move to set the tone.")
            )
            if first_cut_mode and not preview_assist.get("needs_help")
            else (
                tr("The first clip is in. Try one quick move, then switch to draft preview if playback gets heavy.")
                if first_cut_mode
                else (
                    tr("Start here for the quickest changes.")
                    if not preview_assist.get("needs_help")
                    else tr("Start here for the quickest changes. Draft preview is ready if playback gets heavy.")
                )
            )
        ),
        "actions": actions,
        "clip_ids": clip_ids,
        "visual_clip_ids": visual_clip_ids,
        "primary_clip_id": primary_clip_id,
        "is_first_cut": first_cut_mode,
        "selection_mode": "implicit" if implicit_selection else "explicit",
        "datamosh_target": datamosh_target,
        "effect_target": effect_target,
        "preview_assist": preview_assist,
        "proxy_status": proxy_status,
    }


class QuickActionDockPanel(QFrame):
    """Top-level quick favorites for the simple editing path."""

    advanced_toggled = pyqtSignal(bool)
    quick_target_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        tr = getattr(get_app(), "_tr", lambda text: text)

        self._selection = []
        self._target = None
        self._advanced_visible = True
        self._show_more_actions = bool(get_app().get_settings().get("quick-edit-show-more-actions"))
        self._action_buttons = {}
        self._proxy_action_buttons = {}
        self.setObjectName("quickActionDockPanel")
        self.setFrameShape(QFrame.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        header = QLabel(f"<strong>{tr('Quick Actions')}</strong>", self)
        header.setTextFormat(header.textFormat())
        root.addWidget(header)

        self.summary_label = QLabel(tr("Select a clip or handoff to see quick moves."), self)
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.hint_label = QLabel(
            tr("These are the simplest high-impact moves. Detailed controls stay below when you need them."),
            self,
        )
        self.hint_label.setWordWrap(True)
        root.addWidget(self.hint_label)

        self.action_grid = QGridLayout()
        self.action_grid.setContentsMargins(0, 0, 0, 0)
        self.action_grid.setHorizontalSpacing(8)
        self.action_grid.setVerticalSpacing(8)
        root.addLayout(self.action_grid)

        self.more_actions_button = QPushButton(self)
        self.more_actions_button.setMinimumHeight(32)
        self.more_actions_button.clicked.connect(self._toggle_more_actions)
        self.more_actions_button.hide()
        root.addWidget(self.more_actions_button)

        self.preview_status_frame = QFrame(self)
        self.preview_status_frame.setFrameShape(QFrame.StyledPanel)
        preview_root = QVBoxLayout(self.preview_status_frame)
        preview_root.setContentsMargins(10, 10, 10, 10)
        preview_root.setSpacing(8)

        self.preview_status_header = QLabel(f"<strong>{tr('Preview Status')}</strong>", self.preview_status_frame)
        preview_root.addWidget(self.preview_status_header)

        self.preview_status_label = QLabel(self.preview_status_frame)
        self.preview_status_label.setWordWrap(True)
        preview_root.addWidget(self.preview_status_label)

        self.preview_status_detail_label = QLabel(self.preview_status_frame)
        self.preview_status_detail_label.setWordWrap(True)
        preview_root.addWidget(self.preview_status_detail_label)

        self.preview_status_grid = QGridLayout()
        self.preview_status_grid.setContentsMargins(0, 0, 0, 0)
        self.preview_status_grid.setHorizontalSpacing(8)
        self.preview_status_grid.setVerticalSpacing(8)
        preview_root.addLayout(self.preview_status_grid)
        self.preview_status_frame.hide()
        root.addWidget(self.preview_status_frame)

        self.advanced_button = QPushButton(self)
        self.advanced_button.setMinimumHeight(32)
        self.advanced_button.clicked.connect(self._toggle_advanced)
        root.addWidget(self.advanced_button)

        self.advanced_label = QLabel(self)
        self.advanced_label.setWordWrap(True)
        root.addWidget(self.advanced_label)

        window = getattr(get_app(), "window", None)
        if window and getattr(window, "propertyTableView", None):
            window.propertyTableView.loadProperties.connect(self.update_selection)
        proxy_service = getattr(window, "proxy_service", None) if window else None
        if proxy_service:
            proxy_service.file_job_changed.connect(lambda _file_id: self.refresh_from_current_selection())
            proxy_service.job_finished.connect(lambda _file_id, _status: self.refresh_from_current_selection())

        self.set_advanced_visible(True)
        self.hide()

    def _clear_action_buttons(self):
        while self.action_grid.count():
            item = self.action_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._action_buttons = {}

    def _clear_proxy_action_buttons(self):
        while self.preview_status_grid.count():
            item = self.preview_status_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._proxy_action_buttons = {}

    def _set_show_more_actions(self, show_more, persist=True):
        self._show_more_actions = bool(show_more)
        if persist:
            get_app().get_settings().set("quick-edit-show-more-actions", self._show_more_actions)

    def _set_more_actions_state(self, display_state):
        display_state = display_state if isinstance(display_state, dict) else {}
        if not display_state.get("has_overflow"):
            self.more_actions_button.hide()
            self.more_actions_button.setText("")
            return
        self.more_actions_button.setText(str(display_state.get("toggle_label") or ""))
        self.more_actions_button.show()

    def _rebuild_action_buttons(self, actions):
        self._clear_action_buttons()
        for index, action in enumerate(actions or []):
            action_key = str(action.get("key") or "")
            button = QPushButton(str(action.get("label") or action_key), self)
            button.setMinimumHeight(34)
            button.setToolTip(str(action.get("description") or ""))
            button.setEnabled(bool(action.get("enabled")))
            button.clicked.connect(lambda _checked=False, key=action_key: self._run_action(key))
            self.action_grid.addWidget(button, index // 3, index % 3)
            self._action_buttons[action_key] = button

    def _set_proxy_status(self, proxy_status):
        proxy_status = proxy_status if isinstance(proxy_status, dict) else {}
        if not proxy_status.get("visible"):
            self.preview_status_frame.hide()
            self.preview_status_label.clear()
            self.preview_status_detail_label.clear()
            self._clear_proxy_action_buttons()
            return

        self.preview_status_label.setText(sanitize_ui_text(str(proxy_status.get("headline") or "")))
        self.preview_status_detail_label.setText(sanitize_ui_text(str(proxy_status.get("detail") or "")))
        self._clear_proxy_action_buttons()
        for index, action in enumerate(proxy_status.get("actions") or []):
            action_key = str(action.get("key") or "")
            button = QPushButton(str(action.get("label") or action_key), self.preview_status_frame)
            button.setMinimumHeight(32)
            button.setToolTip(str(action.get("description") or ""))
            button.clicked.connect(lambda _checked=False, key=action_key: self._run_action(key))
            self.preview_status_grid.addWidget(button, index // 3, index % 3)
            self._proxy_action_buttons[action_key] = button
        self.preview_status_frame.show()

    def set_advanced_visible(self, visible):
        self._advanced_visible = bool(visible)
        tr = get_app()._tr
        if self._advanced_visible:
            self.advanced_button.setText(tr("Hide Detailed Properties"))
            self.advanced_label.setText(
                sanitize_ui_text(tr("Detailed property editing is visible below for fine-tuning."))
            )
        else:
            self.advanced_button.setText(tr("Show Detailed Properties"))
            self.advanced_label.setText(
                sanitize_ui_text(tr("Detailed properties are tucked away to keep the dock clean."))
            )

    def _toggle_advanced(self):
        self.advanced_toggled.emit(not self._advanced_visible)

    def _toggle_more_actions(self):
        self._set_show_more_actions(not self._show_more_actions)
        self.refresh_from_current_selection()

    def refresh_from_current_selection(self):
        window = getattr(get_app(), "window", None)
        selection = list(getattr(window, "selected_items", []) or []) if window else []
        self.update_selection(selection)

    def update_selection(self, selection):
        self._selection = list(selection or [])
        window = getattr(get_app(), "window", None)
        preview_mode = window.preview_performance_mode() if window and hasattr(window, "preview_performance_mode") else PREVIEW_PERFORMANCE_MODE_DEFAULT
        target = resolve_quick_action_target(self._selection, tr=get_app()._tr, preview_mode=preview_mode)
        self._target = target
        should_show = bool(target.get("enabled"))

        if not should_show:
            self.summary_label.setText(
                sanitize_ui_text(str(target.get("summary") or get_app()._tr("Quick Actions")))
            )
            self.hint_label.setText(
                sanitize_ui_text(
                    str(target.get("message") or get_app()._tr("Select a clip or handoff to see quick moves."))
                )
            )
            self._clear_action_buttons()
            self._set_more_actions_state({"has_overflow": False})
            self._set_proxy_status({"visible": False})
            self.hide()
            self.quick_target_changed.emit(False)
            return

        display_state = build_quick_action_display_state(target, show_more=self._show_more_actions, tr=get_app()._tr)
        self.summary_label.setText(
            sanitize_ui_text(str(target.get("summary") or get_app()._tr("Quick Actions")))
        )
        self.hint_label.setText(sanitize_ui_text(str(target.get("message") or "")))
        self._rebuild_action_buttons(display_state.get("visible_actions") or [])
        self._set_more_actions_state(display_state)
        self._set_proxy_status(target.get("proxy_status"))
        self.show()
        self.quick_target_changed.emit(True)

    def _run_action(self, action_key):
        if not self._target or not action_key:
            return
        window = getattr(get_app(), "window", None)
        timeline = getattr(window, "timeline", None) if window else None
        datamosh_service = getattr(window, "datamosh_service", None) if window else None
        clip_ids = list(self._target.get("clip_ids") or [])
        visual_clip_ids = list(self._target.get("visual_clip_ids") or [])
        primary_clip_id = str(self._target.get("primary_clip_id") or "")

        if action_key == "clip_punch_zoom" and timeline:
            timeline.Apply_Effect_Card_Preset(
                visual_clip_ids,
                "punch_zoom",
                amount_key=EFFECT_CARD_AMOUNT_DEFAULT_KEY,
            )
        elif action_key == "clip_speed_double" and timeline:
            timeline.apply_relative_speed_preset(clip_ids, 2.0)
        elif action_key == "clip_reverse" and timeline:
            timeline.toggle_retime_direction(clip_ids)
        elif action_key == "clip_freeze" and timeline:
            timeline.apply_freeze_marker(clip_ids, 1.0, zoom=False)
        elif action_key == "clip_freeze_hit" and timeline:
            timeline.apply_freeze_marker(clip_ids, 1.0, zoom=True)
        elif action_key == "clip_jugg_shake" and timeline:
            timeline.Apply_Effect_Card_Preset(
                visual_clip_ids,
                "jugg_shake",
                amount_key=EFFECT_CARD_AMOUNT_DEFAULT_KEY,
            )
        elif action_key == "clip_cut_mosh" and datamosh_service and primary_clip_id:
            datamosh_service.generate_for_clip(
                primary_clip_id,
                "cut_mosh",
                amount_key=DATAMOSH_AMOUNT_DEFAULT_KEY,
            )
        elif action_key == "preview_toggle_quality" and window and hasattr(window, "set_preview_performance_mode"):
            current_mode = window.preview_performance_mode()
            next_mode = "quality" if current_mode == "draft" else "draft"
            window.set_preview_performance_mode(next_mode)
        elif action_key == "preview_optimize" and window:
            preview_assist = self._target.get("preview_assist") or {}
            file_ids = [str(file_id or "") for file_id in preview_assist.get("file_ids") or [] if str(file_id or "")]
            if file_ids:
                window._optimized_preview_target_file_ids = file_ids
                window.actionOptimizedPreviewCreate_trigger()
        elif action_key == "preview_proxy_rebuild" and window and hasattr(window, "actionOptimizedPreviewRebuild_trigger"):
            proxy_status = self._target.get("proxy_status") or {}
            file_ids = [str(file_id or "") for file_id in proxy_status.get("file_ids") or [] if str(file_id or "")]
            if file_ids:
                window._optimized_preview_target_file_ids = file_ids
                window.actionOptimizedPreviewRebuild_trigger()
        elif action_key == "preview_proxy_remove" and window:
            proxy_status = self._target.get("proxy_status") or {}
            file_ids = [str(file_id or "") for file_id in proxy_status.get("file_ids") or [] if str(file_id or "")]
            if file_ids:
                window._optimized_preview_target_file_ids = file_ids
                window.actionOptimizedPreviewRemove_trigger()
        elif action_key == "preview_proxy_cancel" and window:
            proxy_status = self._target.get("proxy_status") or {}
            file_ids = [str(file_id or "") for file_id in proxy_status.get("file_ids") or [] if str(file_id or "")]
            if file_ids:
                window._optimized_preview_target_file_ids = file_ids
                window.actionOptimizedPreviewCancel_trigger()
        elif action_key == "preview_cache_clear" and window and hasattr(window, "clear_preview_cache"):
            window.clear_preview_cache()
        elif action_key == "transition_jugg_shake" and timeline:
            timeline.Apply_Transition_Style_Preset(
                "shake_cut",
                timing_key="overlap",
                fallback_bpm=120.0,
                amount_key="default",
            )
        elif action_key == "transition_whip_push" and timeline:
            timeline.Apply_Transition_Style_Preset(
                "whip_push",
                timing_key="half_beat",
                fallback_bpm=120.0,
                amount_key="default",
            )
        elif action_key == "transition_find_hit" and timeline:
            timeline.Apply_Transition_Beat_Marker_Helper("find_hit", fallback_bpm=120.0)
        elif action_key == "transition_beat_pair" and timeline:
            timeline.Apply_Transition_Beat_Marker_Helper("beat_pair", fallback_bpm=120.0)

        self.refresh_from_current_selection()
