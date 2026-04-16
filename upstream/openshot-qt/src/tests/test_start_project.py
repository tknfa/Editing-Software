"""
 @file
 @brief Unit tests for lightweight project-start helpers
"""

import os
import sys
import unittest


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from windows.views.start_project import build_start_project_state


class StartProjectHelperTests(unittest.TestCase):
    def test_build_start_project_state_for_empty_project_surfaces_import_actions(self):
        state = build_start_project_state("", [], [], selected_file_ids=[])

        self.assertTrue(state["visible"])
        self.assertEqual(state["mode"], "empty")
        self.assertEqual(
            [action["key"] for action in state["actions"]],
            ["import_files", "open_project"],
        )
        self.assertEqual(state["eyebrow"], "Project: Untitled Project")
        self.assertEqual(state["headline"], "Bring in footage to start the first cut")
        self.assertEqual(state["inventory"], "Bin: nothing imported yet")
        self.assertIn("Finder", state["note"])
        self.assertEqual(state["primary_action_key"], "import_files")

    def test_build_start_project_state_prefers_selected_files_for_first_timeline_add(self):
        files = [
            {"id": "F1", "path": "/tmp/one.mp4", "name": "one.mp4", "media_type": "video"},
            {"id": "F2", "path": "/tmp/two.mp4", "name": "two.mp4", "media_type": "video"},
        ]

        state = build_start_project_state(
            "/tmp/Edit.osp",
            files,
            [],
            selected_file_ids=["F2"],
        )

        self.assertTrue(state["visible"])
        self.assertEqual(state["mode"], "ready")
        self.assertEqual(state["default_file_ids"], ["F2"])
        self.assertEqual(state["primary_action_key"], "add_to_timeline")
        self.assertEqual(state["actions"][0]["key"], "add_to_timeline")
        self.assertEqual(state["actions"][0]["label"], "Add Selected Video to Timeline")
        self.assertEqual(state["inventory"], "Selected: 1 video | Bin: 2 videos")

    def test_build_start_project_state_falls_back_to_first_file_when_none_selected(self):
        files = [
            {"id": "F1", "path": "/tmp/one.mp4", "name": "one.mp4", "media_type": "video"},
            {"id": "F2", "path": "/tmp/two.mp4", "name": "two.mp4", "media_type": "video"},
        ]

        state = build_start_project_state(
            "/tmp/Edit.osp",
            files,
            [],
            selected_file_ids=[],
        )

        self.assertEqual(state["default_file_ids"], ["F1"])
        self.assertEqual(state["actions"][0]["label"], "Add First Video to Timeline")

    def test_build_start_project_state_prefers_video_when_bin_is_mixed_and_nothing_selected(self):
        files = [
            {"id": "A1", "path": "/tmp/theme.mp3", "name": "theme.mp3", "media_type": "audio", "has_audio": True, "has_video": False},
            {"id": "I1", "path": "/tmp/card.png", "name": "card.png", "media_type": "image", "has_audio": False, "has_video": True},
            {"id": "V1", "path": "/tmp/intro.mp4", "name": "intro.mp4", "media_type": "video", "has_audio": True, "has_video": True},
        ]

        state = build_start_project_state(
            "/tmp/Edit.osp",
            files,
            [],
            selected_file_ids=[],
        )

        self.assertEqual(state["default_file_ids"], ["V1"])
        self.assertEqual(state["actions"][0]["label"], "Add First Video to Timeline")
        self.assertEqual(state["inventory"], "Bin: 1 video | 1 image | 1 audio file")
        self.assertIn("video clip", state["detail"])

    def test_build_start_project_state_explains_audio_selection_when_visuals_exist(self):
        files = [
            {"id": "A1", "path": "/tmp/theme.mp3", "name": "theme.mp3", "media_type": "audio", "has_audio": True, "has_video": False},
            {"id": "V1", "path": "/tmp/intro.mp4", "name": "intro.mp4", "media_type": "video", "has_audio": True, "has_video": True},
        ]

        state = build_start_project_state(
            "/tmp/Edit.osp",
            files,
            [],
            selected_file_ids=["A1"],
        )

        self.assertEqual(state["default_file_ids"], ["A1"])
        self.assertEqual(state["headline"], "Selected audio is ready for the timeline")
        self.assertEqual(state["actions"][0]["label"], "Add Selected Audio to Timeline")
        self.assertEqual(state["inventory"], "Selected: 1 audio file | Bin: 1 video | 1 audio file")
        self.assertIn("video or image", state["detail"])

    def test_build_start_project_state_reports_selected_visual_inventory_when_audio_is_also_imported(self):
        files = [
            {"id": "A1", "path": "/tmp/theme.mp3", "name": "theme.mp3", "media_type": "audio", "has_audio": True, "has_video": False},
            {"id": "I1", "path": "/tmp/card.png", "name": "card.png", "media_type": "image", "has_audio": False, "has_video": True},
            {"id": "V1", "path": "/tmp/intro.mp4", "name": "intro.mp4", "media_type": "video", "has_audio": True, "has_video": True},
        ]

        state = build_start_project_state(
            "/tmp/Edit.osp",
            files,
            [],
            selected_file_ids=["I1", "V1"],
        )

        self.assertEqual(state["inventory"], "Selected: 2 visuals | Bin: 1 video | 1 image | 1 audio file")
        self.assertIn("Selected visual media", state["headline"])

    def test_build_start_project_state_hides_after_timeline_has_clips(self):
        files = [
            {"id": "F1", "path": "/tmp/one.mp4", "name": "one.mp4", "media_type": "video"},
        ]
        clips = [
            {"id": "C1", "file_id": "F1", "position": 0.0, "start": 0.0, "end": 1.0},
        ]

        state = build_start_project_state(
            "/tmp/Edit.osp",
            files,
            clips,
            selected_file_ids=["F1"],
        )

        self.assertFalse(state["visible"])
        self.assertEqual(state["mode"], "editing")
        self.assertEqual(state["inventory"], "")
        self.assertEqual(state["primary_action_key"], "")


if __name__ == "__main__":
    unittest.main()
