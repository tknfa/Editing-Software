"""
 @file
 @brief Unit tests for quick-action helper resolution
"""

import os
import sys
import unittest
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from classes import ui_text
from windows.views.quick_actions import build_quick_action_display_state, resolve_quick_action_target


class DummyClip:
    def __init__(self, data, title="Clip"):
        self.data = data
        self._title = title

    def title(self):
        return self._title


class QuickActionHelperTests(unittest.TestCase):
    def test_resolve_quick_action_target_promotes_first_cut_presets_for_early_visual_clip(self):
        clip = DummyClip(
            {
                "id": "clip-1",
                "reader": {"path": __file__, "has_video": True, "has_single_image": False},
                "start": 0.0,
                "end": 2.0,
            },
            title="Main Take",
        )
        target = resolve_quick_action_target(
            [{"id": "clip-1", "type": "clip"}],
            clip_lookup=lambda clip_id: clip if clip_id == "clip-1" else None,
            project_clips=[{"id": "clip-1"}],
            project_transitions=[],
        )

        self.assertTrue(target["enabled"])
        self.assertTrue(target["is_first_cut"])
        self.assertEqual(target["selection_mode"], "explicit")
        self.assertIn("First cut moves", target["summary"])
        self.assertIn("set the tone", target["message"])
        self.assertEqual(
            [action["key"] for action in target["actions"][:5]],
            [
                "clip_punch_zoom",
                "clip_jugg_shake",
                "clip_freeze_hit",
                "clip_cut_mosh",
                "clip_speed_double",
            ],
        )

    def test_resolve_quick_action_target_uses_only_timeline_clip_as_implicit_target(self):
        clip = DummyClip(
            {
                "id": "clip-1",
                "reader": {"path": __file__, "has_video": True, "has_single_image": False},
                "start": 0.0,
                "end": 2.0,
            },
            title="Main Take",
        )
        target = resolve_quick_action_target(
            [],
            clip_lookup=lambda clip_id: clip if clip_id == "clip-1" else None,
            project_clips=[{"id": "clip-1"}],
            project_transitions=[],
        )

        self.assertTrue(target["enabled"])
        self.assertEqual(target["primary_clip_id"], "clip-1")
        self.assertEqual(target["selection_mode"], "implicit")
        self.assertTrue(target["is_first_cut"])
        self.assertIn("set the tone", target["message"])

    def test_resolve_quick_action_target_for_single_visual_clip_enables_clip_favorites(self):
        clip = DummyClip(
            {
                "reader": {"path": __file__, "has_video": True, "has_single_image": False},
                "start": 0.0,
                "end": 2.0,
            },
            title="Main Take",
        )
        target = resolve_quick_action_target(
            [{"id": "clip-1", "type": "clip"}],
            clip_lookup=lambda clip_id: clip if clip_id == "clip-1" else None,
        )
        action_map = {action["key"]: action for action in target["actions"]}

        self.assertTrue(target["enabled"])
        self.assertEqual(target["context"], "clip")
        self.assertIn("Main Take", target["summary"])
        self.assertTrue(action_map["clip_jugg_shake"]["enabled"])
        self.assertTrue(action_map["clip_cut_mosh"]["enabled"])

    def test_resolve_quick_action_target_sanitizes_emoji_titles_on_macos(self):
        clip = DummyClip(
            {
                "reader": {"path": __file__, "has_video": True, "has_single_image": False},
                "start": 0.0,
                "end": 2.0,
            },
            title="Main Take 🤯",
        )
        with patch.object(ui_text.platform, "system", return_value="Darwin"):
            target = resolve_quick_action_target(
                [{"id": "clip-1", "type": "clip"}],
                clip_lookup=lambda clip_id: clip if clip_id == "clip-1" else None,
            )

        self.assertIn("Main Take ?", target["summary"])
        self.assertNotIn("🤯", target["summary"])

    def test_resolve_quick_action_target_for_multi_clip_selection_disables_datamosh_favorite(self):
        clip = DummyClip(
            {
                "reader": {"path": __file__, "has_video": True, "has_single_image": False},
                "start": 0.0,
                "end": 2.0,
            },
            title="Main Take",
        )
        target = resolve_quick_action_target(
            [
                {"id": "clip-1", "type": "clip"},
                {"id": "clip-2", "type": "clip"},
            ],
            clip_lookup=lambda _clip_id: clip,
            transition_target_resolver=lambda *args, **kwargs: {"enabled": False},
        )
        action_map = {action["key"]: action for action in target["actions"]}

        self.assertEqual(target["context"], "clip")
        self.assertEqual(target["primary_clip_id"], "")
        self.assertTrue(action_map["clip_jugg_shake"]["enabled"])
        self.assertFalse(action_map["clip_cut_mosh"]["enabled"])

    def test_resolve_quick_action_target_returns_normal_clip_actions_after_first_cut_stage(self):
        clip = DummyClip(
            {
                "id": "clip-1",
                "reader": {"path": __file__, "has_video": True, "has_single_image": False},
                "start": 0.0,
                "end": 2.0,
            },
            title="Main Take",
        )
        target = resolve_quick_action_target(
            [{"id": "clip-1", "type": "clip"}],
            clip_lookup=lambda clip_id: clip if clip_id == "clip-1" else None,
            project_clips=[{"id": "clip-1"}, {"id": "clip-2"}, {"id": "clip-3"}],
            project_transitions=[],
            transition_target_resolver=lambda *args, **kwargs: {"enabled": False},
        )

        self.assertFalse(target["is_first_cut"])
        self.assertEqual(
            [action["key"] for action in target["actions"][:3]],
            ["clip_jugg_shake", "clip_cut_mosh", "clip_speed_double"],
        )

    def test_resolve_quick_action_target_prefers_transition_context_when_available(self):
        target = resolve_quick_action_target(
            [{"id": "transition-1", "type": "transition"}],
            transition_target_resolver=lambda selection, tr=None: {
                "enabled": True,
                "summary": "Clip A -> Clip B",
                "selection": selection,
            },
            effect_target_resolver=lambda *args, **kwargs: {"enabled": False, "clip_ids": []},
            datamosh_target_resolver=lambda *args, **kwargs: {"enabled": False},
        )

        self.assertTrue(target["enabled"])
        self.assertEqual(target["context"], "transition")
        self.assertEqual(
            [action["key"] for action in target["actions"]],
            [
                "transition_jugg_shake",
                "transition_whip_push",
                "transition_find_hit",
                "transition_beat_pair",
                "preview_toggle_quality",
            ],
        )

    def test_resolve_quick_action_target_handles_empty_selection(self):
        target = resolve_quick_action_target([])
        self.assertFalse(target["enabled"])
        self.assertEqual(target["message"], "Select a clip or handoff to see quick moves.")
        self.assertEqual(target["actions"], [])

    def test_resolve_quick_action_target_adds_preview_helpers_for_heavy_clip(self):
        clip = DummyClip(
            {
                "file_id": "file-1",
                "reader": {
                    "id": "file-1",
                    "path": __file__,
                    "has_video": True,
                    "has_single_image": False,
                },
                "effects": [{"id": "fx-1"}],
                "start": 0.0,
                "end": 2.0,
            },
            title="Styled Clip",
        )
        target = resolve_quick_action_target(
            [{"id": "clip-1", "type": "clip"}],
            clip_lookup=lambda clip_id: clip if clip_id == "clip-1" else None,
            has_proxy_reader_lookup=lambda _file_id: False,
            proxy_state_lookup=lambda _file_id: "none",
            transition_target_resolver=lambda *args, **kwargs: {"enabled": False},
        )
        action_map = {action["key"]: action for action in target["actions"]}

        self.assertIn("preview_toggle_quality", action_map)
        self.assertIn("preview_optimize", action_map)
        self.assertEqual(action_map["preview_toggle_quality"]["label"], "Draft Preview")
        self.assertTrue(target["proxy_status"]["visible"])
        self.assertEqual(
            [action["key"] for action in target["proxy_status"]["actions"]],
            ["preview_proxy_rebuild", "preview_cache_clear"],
        )

    def test_resolve_quick_action_target_hides_preview_optimize_when_proxy_ready(self):
        clip = DummyClip(
            {
                "file_id": "file-2",
                "reader": {
                    "id": "file-2",
                    "path": __file__,
                    "has_video": True,
                    "has_single_image": False,
                },
                "time": {"Points": [{"co": {"X": 1.0, "Y": 0.5}}]},
                "start": 0.0,
                "end": 2.0,
            },
            title="Retime Clip",
        )
        target = resolve_quick_action_target(
            [{"id": "clip-1", "type": "clip"}],
            clip_lookup=lambda clip_id: clip if clip_id == "clip-1" else None,
            has_proxy_reader_lookup=lambda _file_id: True,
            proxy_state_lookup=lambda _file_id: "ready",
            preview_mode="draft",
            transition_target_resolver=lambda *args, **kwargs: {"enabled": False},
        )
        action_map = {action["key"]: action for action in target["actions"]}

        self.assertIn("preview_toggle_quality", action_map)
        self.assertNotIn("preview_optimize", action_map)
        self.assertEqual(action_map["preview_toggle_quality"]["label"], "Full Preview")
        self.assertEqual(
            [action["key"] for action in target["proxy_status"]["actions"]],
            ["preview_proxy_rebuild", "preview_proxy_remove", "preview_cache_clear"],
        )

    def test_build_quick_action_display_state_prioritizes_three_primary_clip_favorites(self):
        target = {
            "context": "clip",
            "actions": [
                {"key": "clip_jugg_shake", "enabled": True},
                {"key": "clip_cut_mosh", "enabled": True},
                {"key": "clip_speed_double", "enabled": True},
                {"key": "clip_reverse", "enabled": True},
                {"key": "clip_freeze", "enabled": True},
                {"key": "preview_toggle_quality", "enabled": True},
            ],
        }

        display_state = build_quick_action_display_state(target, show_more=False)

        self.assertEqual(
            [action["key"] for action in display_state["visible_actions"]],
            ["clip_jugg_shake", "clip_cut_mosh", "clip_speed_double"],
        )
        self.assertTrue(display_state["has_overflow"])
        self.assertEqual(display_state["toggle_label"], "Show 3 More")

    def test_build_quick_action_display_state_hides_disabled_actions_from_compact_row(self):
        target = {
            "context": "clip",
            "actions": [
                {"key": "clip_jugg_shake", "enabled": False},
                {"key": "clip_cut_mosh", "enabled": False},
                {"key": "clip_speed_double", "enabled": True},
                {"key": "clip_reverse", "enabled": True},
                {"key": "clip_freeze", "enabled": True},
            ],
        }

        display_state = build_quick_action_display_state(target, show_more=False)

        self.assertEqual(
            [action["key"] for action in display_state["visible_actions"]],
            ["clip_speed_double", "clip_reverse", "clip_freeze"],
        )
        self.assertFalse(display_state["has_overflow"])

    def test_build_quick_action_display_state_expands_to_all_enabled_actions(self):
        target = {
            "context": "transition",
            "actions": [
                {"key": "transition_jugg_shake", "enabled": True},
                {"key": "transition_whip_push", "enabled": True},
                {"key": "transition_find_hit", "enabled": True},
                {"key": "transition_beat_pair", "enabled": True},
                {"key": "preview_toggle_quality", "enabled": True},
            ],
        }

        display_state = build_quick_action_display_state(target, show_more=True)

        self.assertEqual(
            [action["key"] for action in display_state["visible_actions"]],
            [
                "transition_jugg_shake",
                "transition_whip_push",
                "transition_find_hit",
                "transition_beat_pair",
                "preview_toggle_quality",
            ],
        )
        self.assertTrue(display_state["has_overflow"])
        self.assertEqual(display_state["toggle_label"], "Show Fewer")


if __name__ == "__main__":
    unittest.main()
