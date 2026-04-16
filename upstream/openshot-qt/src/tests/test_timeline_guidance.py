"""
 @file
 @brief Unit tests for early timeline guidance helpers
"""

import os
import sys
import unittest


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from windows.views.timeline_guidance import build_timeline_guidance_state


class TimelineGuidanceHelperTests(unittest.TestCase):
    def test_build_timeline_guidance_state_suggests_adding_another_clip(self):
        files = [
            {"id": "F1", "path": "/tmp/one.mp4", "name": "one.mp4", "media_type": "video"},
            {"id": "F2", "path": "/tmp/two.mp4", "name": "two.mp4", "media_type": "video"},
        ]
        clips = [
            {
                "id": "C1",
                "file_id": "F1",
                "position": 0.0,
                "start": 0.0,
                "end": 2.0,
                "layer": 4,
                "reader": {"path": "/tmp/one.mp4", "has_video": True, "has_single_image": False},
            },
        ]

        state = build_timeline_guidance_state(files, clips, [])

        self.assertTrue(state["visible"])
        self.assertEqual(state["mode"], "build_handoff")
        self.assertEqual(state["headline"], "Next move: add the second shot")
        self.assertEqual(state["action_key"], "add_next_clip")
        self.assertEqual(state["action_label"], "Add Another Clip")
        self.assertEqual(state["file_ids"], ["F2"])
        self.assertAlmostEqual(state["start_position"], 1.875)
        self.assertEqual(state["track_number"], 4)
        self.assertIn("beat-sized overlap", state["detail"])

    def test_build_timeline_guidance_state_uses_marker_for_second_clip_default(self):
        files = [
            {"id": "F1", "path": "/tmp/one.mp4", "name": "one.mp4", "media_type": "video"},
            {"id": "F2", "path": "/tmp/two.mp4", "name": "two.mp4", "media_type": "video"},
        ]
        clips = [
            {
                "id": "C1",
                "file_id": "F1",
                "position": 0.0,
                "start": 0.0,
                "end": 2.0,
                "layer": 4,
                "reader": {"path": "/tmp/one.mp4", "has_video": True, "has_single_image": False},
            },
        ]
        markers = [
            {"id": "M1", "position": 1.82},
        ]

        state = build_timeline_guidance_state(files, clips, [], markers=markers)

        self.assertAlmostEqual(state["start_position"], 1.82)
        self.assertEqual(state["track_number"], 4)
        self.assertIn("marker", state["detail"])

    def test_build_timeline_guidance_state_suggests_selecting_pair_before_overlap(self):
        clips = [
            {
                "id": "C1",
                "file_id": "F1",
                "position": 0.0,
                "start": 0.0,
                "end": 2.0,
                "layer": 4,
                "reader": {"path": "/tmp/one.mp4", "has_video": True, "has_single_image": False},
            },
            {
                "id": "C2",
                "file_id": "F2",
                "position": 2.1,
                "start": 0.0,
                "end": 4.1,
                "layer": 4,
                "reader": {"path": "/tmp/two.mp4", "has_video": True, "has_single_image": False},
            },
        ]

        state = build_timeline_guidance_state([], clips, [])

        self.assertTrue(state["visible"])
        self.assertEqual(state["mode"], "create_handoff")
        self.assertEqual(state["headline"], "Next move: create the first cut")
        self.assertEqual(state["action_key"], "select_handoff")
        self.assertEqual(state["action_label"], "Select First Cut")
        self.assertEqual(state["clip_ids"], ["C1", "C2"])
        self.assertAlmostEqual(state["anchor_position"], 2.0)

    def test_build_timeline_guidance_state_suggests_styling_when_overlap_exists(self):
        clips = [
            {
                "id": "C1",
                "file_id": "F1",
                "position": 0.0,
                "start": 0.0,
                "end": 2.0,
                "layer": 4,
                "reader": {"path": "/tmp/one.mp4", "has_video": True, "has_single_image": False},
            },
            {
                "id": "C2",
                "file_id": "F2",
                "position": 1.5,
                "start": 0.0,
                "end": 3.5,
                "layer": 4,
                "reader": {"path": "/tmp/two.mp4", "has_video": True, "has_single_image": False},
            },
        ]

        state = build_timeline_guidance_state([], clips, [])

        self.assertTrue(state["visible"])
        self.assertEqual(state["mode"], "style_handoff")
        self.assertEqual(state["headline"], "Next move: style the first cut")
        self.assertEqual(state["action_label"], "Select First Cut")
        self.assertEqual(state["clip_ids"], ["C1", "C2"])
        self.assertAlmostEqual(state["anchor_position"], 1.75)

    def test_build_timeline_guidance_state_hides_once_transition_exists(self):
        clips = [
            {
                "id": "C1",
                "file_id": "F1",
                "position": 0.0,
                "start": 0.0,
                "end": 2.0,
                "layer": 4,
                "reader": {"path": "/tmp/one.mp4", "has_video": True, "has_single_image": False},
            },
            {
                "id": "C2",
                "file_id": "F2",
                "position": 1.5,
                "start": 0.0,
                "end": 3.5,
                "layer": 4,
                "reader": {"path": "/tmp/two.mp4", "has_video": True, "has_single_image": False},
            },
        ]
        transitions = [
            {"id": "T1", "position": 1.5, "start": 0.0, "end": 0.5, "layer": 4},
        ]

        state = build_timeline_guidance_state([], clips, transitions)

        self.assertFalse(state["visible"])
        self.assertEqual(state["mode"], "hidden")


if __name__ == "__main__":
    unittest.main()
