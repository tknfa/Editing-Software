"""
 @file
 @brief Workspace cleanup helpers for the personal quick-edit flow
"""


WORKSPACE_MODE_SIMPLE = "simple"
WORKSPACE_MODE_FULL = "full"
WORKSPACE_MODE_DEFAULT = WORKSPACE_MODE_SIMPLE

WORKSPACE_SIMPLE_VISIBLE_DOCKS = (
    "dockFiles",
    "dockVideo",
    "dockProperties",
    "dockTimeline",
)
WORKSPACE_SIMPLE_HIDDEN_DOCKS = (
    "dockTransitions",
    "dockEffects",
    "dockEmojis",
    "dockCaptionEditor",
    "dockTutorial",
)

WORKSPACE_FULL_VISIBLE_DOCKS = (
    "dockFiles",
    "dockVideo",
    "dockProperties",
    "dockTransitions",
    "dockEffects",
    "dockEmojis",
    "dockTimeline",
)
WORKSPACE_FULL_HIDDEN_DOCKS = (
    "dockCaptionEditor",
    "dockTutorial",
)

WORKSPACE_PREFERRED_DOCK_AREAS = {
    "dockFiles": "top",
    "dockVideo": "top",
    "dockProperties": "left",
    "dockTimeline": "bottom",
    "dockTransitions": "right",
    "dockEffects": "right",
    "dockEmojis": "right",
    "dockCaptionEditor": "right",
    "dockTutorial": "right",
}

WORKSPACE_MENU_SUPPRESSED_ACTIONS = (
    "actionFreeze_View",
    "actionUn_Freeze_View",
    "actionShow_All",
)


def normalize_workspace_mode(mode):
    normalized = str(mode or WORKSPACE_MODE_DEFAULT).strip().lower()
    if normalized not in (WORKSPACE_MODE_SIMPLE, WORKSPACE_MODE_FULL):
        return WORKSPACE_MODE_DEFAULT
    return normalized


def workspace_dock_plan(mode):
    mode = normalize_workspace_mode(mode)
    if mode == WORKSPACE_MODE_FULL:
        return {
            "mode": mode,
            "visible": list(WORKSPACE_FULL_VISIBLE_DOCKS),
            "hidden": list(WORKSPACE_FULL_HIDDEN_DOCKS),
        }
    return {
        "mode": mode,
        "visible": list(WORKSPACE_SIMPLE_VISIBLE_DOCKS),
        "hidden": list(WORKSPACE_SIMPLE_HIDDEN_DOCKS),
    }


def workspace_menu_labels(mode):
    mode = normalize_workspace_mode(mode)
    return {
        "menu_title": "Workspace",
        "simple_action": "Quick Edit Workspace",
        "full_action": "Full Workspace",
        "active_status": "Quick Edit" if mode == WORKSPACE_MODE_SIMPLE else "Full",
    }
