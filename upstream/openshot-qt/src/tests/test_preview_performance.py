"""
 @file
 @brief Unit tests for lightweight preview-performance helpers
"""

import os
import sys
import unittest


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from windows.views.preview_performance import (
    PREVIEW_PERFORMANCE_MODE_DEFAULT,
    build_preview_assist_state,
    build_proxy_status_state,
    clip_has_nontrivial_time_map,
    clip_is_heavy_for_preview,
    collect_preview_file_ids,
    normalize_preview_performance_mode,
    preview_performance_scale_factor,
)


class PreviewPerformanceHelperTests(unittest.TestCase):
    def test_normalize_preview_mode_falls_back_to_default(self):
        self.assertEqual(normalize_preview_performance_mode("mystery"), PREVIEW_PERFORMANCE_MODE_DEFAULT)
        self.assertEqual(preview_performance_scale_factor("draft"), 0.6)

    def test_collect_preview_file_ids_deduplicates_in_order(self):
        file_ids = collect_preview_file_ids(
            [
                {"file_id": "file-1"},
                {"reader": {"id": "file-2"}},
                {"file_id": "file-1"},
                {"reader": {"id": "file-3"}},
            ]
        )

        self.assertEqual(file_ids, ["file-1", "file-2", "file-3"])

    def test_clip_has_nontrivial_time_map_detects_ramps(self):
        self.assertFalse(
            clip_has_nontrivial_time_map(
                {"time": {"Points": [{"co": {"X": 1.0, "Y": 1.0}}]}}
            )
        )
        self.assertTrue(
            clip_has_nontrivial_time_map(
                {"time": {"Points": [{"co": {"X": 1.0, "Y": 0.5}}]}}
            )
        )
        self.assertTrue(
            clip_has_nontrivial_time_map(
                {"time": {"Points": [{"co": {"X": 0.0, "Y": 0.0}}, {"co": {"X": 1.0, "Y": 1.0}}]}}
            )
        )

    def test_clip_is_heavy_for_preview_detects_managed_effects(self):
        self.assertTrue(clip_is_heavy_for_preview({"effects": [{"id": "fx-1"}]}))
        self.assertTrue(
            clip_is_heavy_for_preview(
                {"ui": {"effect_card_preset": "jugg_shake"}}
            )
        )
        self.assertFalse(clip_is_heavy_for_preview({"effects": []}))

    def test_build_preview_assist_state_surfaces_optimize_for_heavy_clips(self):
        state = build_preview_assist_state(
            [
                {
                    "file_id": "file-1",
                    "reader": {"id": "file-1"},
                    "effects": [{"id": "fx-1"}],
                }
            ],
            preview_mode="quality",
            has_proxy_reader_lookup=lambda _file_id: False,
        )

        self.assertTrue(state["needs_help"])
        self.assertEqual(state["file_ids"], ["file-1"])
        self.assertTrue(state["can_optimize"])
        self.assertFalse(state["proxy_ready"])
        self.assertEqual(state["toggle_label"], "Draft Preview")

    def test_build_preview_assist_state_hides_optimize_when_proxy_exists(self):
        state = build_preview_assist_state(
            [
                {
                    "file_id": "file-9",
                    "reader": {"id": "file-9"},
                    "time": {"Points": [{"co": {"X": 1.0, "Y": 0.75}}]},
                }
            ],
            preview_mode="draft",
            has_proxy_reader_lookup=lambda _file_id: True,
        )

        self.assertTrue(state["needs_help"])
        self.assertFalse(state["can_optimize"])
        self.assertTrue(state["proxy_ready"])
        self.assertEqual(state["toggle_label"], "Full Preview")

    def test_build_proxy_status_state_for_ready_preview(self):
        state = build_proxy_status_state(
            ["file-1"],
            preview_mode="draft",
            proxy_state_lookup=lambda _file_id: "ready",
        )

        self.assertTrue(state["visible"])
        self.assertIn("Optimized Preview Ready", state["headline"])
        self.assertEqual(
            [action["key"] for action in state["actions"]],
            ["preview_proxy_rebuild", "preview_proxy_remove", "preview_cache_clear"],
        )

    def test_build_proxy_status_state_for_active_job_uses_cancel(self):
        state = build_proxy_status_state(
            ["file-1", "file-2"],
            preview_mode="quality",
            proxy_state_lookup=lambda file_id: "running" if file_id == "file-1" else "queued",
            proxy_badge_lookup=lambda file_id: {"label": "Creating 37%"} if file_id == "file-1" else {"label": "Queued"},
        )

        self.assertTrue(state["visible"])
        self.assertIn("preview jobs active", state["headline"])
        self.assertEqual(
            [action["key"] for action in state["actions"]],
            ["preview_proxy_cancel", "preview_cache_clear"],
        )


if __name__ == "__main__":
    unittest.main()
