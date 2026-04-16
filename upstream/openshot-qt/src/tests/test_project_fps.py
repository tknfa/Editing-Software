"""
 @file
 @brief Unit tests for compact project FPS helpers
"""

import os
import sys
import unittest


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from windows.views.project_fps import (
    build_project_fps_profile_description,
    build_project_fps_state,
    format_project_fps_label,
    matching_project_fps_preset_key,
)


class ProjectFPSHelperTests(unittest.TestCase):
    def test_format_project_fps_label_handles_integer_and_fractional_rates(self):
        self.assertEqual(format_project_fps_label(30, 1), "30")
        self.assertEqual(format_project_fps_label(30000, 1001), "29.97")
        self.assertEqual(format_project_fps_label(60000, 1001), "59.94")

    def test_matching_project_fps_preset_key_detects_builtin_preset(self):
        self.assertEqual(matching_project_fps_preset_key({"num": 24, "den": 1}), "24")
        self.assertEqual(matching_project_fps_preset_key({"num": 48, "den": 1}), "")

    def test_build_project_fps_state_surfaces_current_rate_and_preset(self):
        state = build_project_fps_state(
            {
                "width": 1920,
                "height": 1080,
                "fps": {"num": 30000, "den": 1001},
            }
        )

        self.assertEqual(state["headline"], "Project FPS: 29.97")
        self.assertEqual(state["current_label"], "29.97")
        self.assertEqual(state["current_preset_key"], "2997")
        self.assertFalse(state["is_custom"])
        self.assertIn("snaps the edit to the new frame grid", state["detail"])

    def test_build_project_fps_state_marks_nonstandard_rate_as_custom(self):
        state = build_project_fps_state(
            {
                "width": 1280,
                "height": 720,
                "fps": {"num": 48, "den": 1},
            }
        )

        self.assertEqual(state["headline"], "Project FPS: 48")
        self.assertTrue(state["is_custom"])
        self.assertEqual(state["current_preset_key"], "")
        self.assertIn("custom 48 fps rate", state["detail"])

    def test_build_project_fps_profile_description_preserves_shape_details(self):
        description = build_project_fps_profile_description(
            {
                "width": 1080,
                "height": 1920,
                "display_ratio": {"num": 9, "den": 16},
                "pixel_ratio": {"num": 1, "den": 1},
            },
            24000,
            1001,
        )

        self.assertEqual(description, "Editing Software 1080x1920 | 23.98 fps | 9:16")


if __name__ == "__main__":
    unittest.main()
