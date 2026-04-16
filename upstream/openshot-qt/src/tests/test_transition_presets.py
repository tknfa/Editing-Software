"""
 @file
 @brief Unit tests for transition preset helpers
"""

import os
import sys
import unittest


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from windows.views.transition_presets import (
    build_transition_beat_marker_plan,
    build_transition_timing_target,
    estimate_beat_interval_seconds,
    find_transition_audio_transient,
    get_transition_style_amount_key,
    get_transition_transient_search_radius,
    get_transition_style_preset_key,
    resolve_transition_overlap_span,
    resolve_transition_style_target,
    scale_transition_style_contrast,
    timeline_item_span,
)


class DummyItem:
    def __init__(self, data):
        self.data = data


class TransitionPresetHelperTests(unittest.TestCase):
    def test_timeline_item_span_uses_visible_timeline_duration(self):
        left_edge, right_edge, duration_s = timeline_item_span(
            {"position": 12.0, "start": 0.0, "end": 0.75}
        )
        self.assertAlmostEqual(left_edge, 12.0)
        self.assertAlmostEqual(right_edge, 12.75)
        self.assertAlmostEqual(duration_s, 0.75)

    def test_get_transition_style_preset_key_prefers_saved_ui_value(self):
        transition_data = {
            "ui": {"transition_style_preset": "glitch_ripple"},
            "reader": {"path": "/tmp/other.svg"},
        }
        self.assertEqual(get_transition_style_preset_key(transition_data), "glitch_ripple")

    def test_get_transition_style_amount_key_defaults_when_preset_exists(self):
        transition_data = {
            "ui": {"transition_style_preset": "glitch_ripple"},
            "reader": {"path": "/tmp/other.svg"},
        }
        self.assertEqual(get_transition_style_amount_key(transition_data), "default")

    def test_resolve_target_prefers_selected_transition(self):
        transition_data = {
            "id": "tran-1",
            "position": 8.0,
            "start": 0.0,
            "end": 0.5,
            "ui": {"transition_style_preset": "shake_cut", "transition_style_amount": "hard"},
        }
        target = resolve_transition_style_target(
            [{"id": "tran-1", "type": "transition"}],
            clip_lookup=lambda _clip_id: None,
            transition_lookup=lambda transition_id: DummyItem(transition_data)
            if transition_id == "tran-1"
            else None,
        )
        self.assertTrue(target["enabled"])
        self.assertEqual(target["mode"], "transition")
        self.assertEqual(target["transition_id"], "tran-1")
        self.assertEqual(target["current_preset_key"], "shake_cut")
        self.assertEqual(target["current_amount_key"], "hard")
        self.assertIn("Selected transition", target["summary"])

    def test_resolve_target_returns_pair_for_overlapping_clips(self):
        clips = {
            "clip-a": DummyItem(
                {"id": "clip-a", "layer": 3, "position": 5.0, "start": 0.0, "end": 2.0}
            ),
            "clip-b": DummyItem(
                {"id": "clip-b", "layer": 3, "position": 6.5, "start": 0.0, "end": 2.0}
            ),
        }
        target = resolve_transition_style_target(
            [
                {"id": "clip-a", "type": "clip"},
                {"id": "clip-b", "type": "clip"},
            ],
            clip_lookup=lambda clip_id: clips.get(clip_id),
            transition_lookup=lambda _transition_id: None,
        )
        self.assertTrue(target["enabled"])
        self.assertEqual(target["mode"], "pair")
        self.assertEqual(target["clip_ids"], ["clip-a", "clip-b"])
        self.assertAlmostEqual(target["position"], 6.5)
        self.assertAlmostEqual(target["duration"], 0.5)

    def test_resolve_target_rejects_non_overlapping_clips(self):
        clips = {
            "clip-a": DummyItem(
                {"id": "clip-a", "layer": 3, "position": 1.0, "start": 0.0, "end": 1.0}
            ),
            "clip-b": DummyItem(
                {"id": "clip-b", "layer": 3, "position": 2.5, "start": 0.0, "end": 1.0}
            ),
        }
        target = resolve_transition_style_target(
            [
                {"id": "clip-a", "type": "clip"},
                {"id": "clip-b", "type": "clip"},
            ],
            clip_lookup=lambda clip_id: clips.get(clip_id),
            transition_lookup=lambda _transition_id: None,
        )
        self.assertFalse(target["enabled"])
        self.assertIn("Overlap", target["message"])

    def test_estimate_beat_interval_prefers_markers_around_anchor(self):
        beat_info = estimate_beat_interval_seconds(8.0, marker_positions=[7.5, 8.0, 8.5], fallback_bpm=120.0)
        self.assertEqual(beat_info["source"], "markers")
        self.assertAlmostEqual(beat_info["beat_duration"], 1.0)

    def test_estimate_beat_interval_falls_back_to_bpm_when_markers_missing(self):
        beat_info = estimate_beat_interval_seconds(8.0, marker_positions=[8.0], fallback_bpm=150.0)
        self.assertEqual(beat_info["source"], "bpm")
        self.assertAlmostEqual(beat_info["beat_duration"], 0.4)

    def test_build_transition_timing_target_clamps_to_overlap_span(self):
        target = {
            "position": 10.0,
            "duration": 0.5,
        }
        adjusted = build_transition_timing_target(
            target,
            "two_beats",
            marker_positions=[9.5, 10.0, 10.5],
            fallback_bpm=120.0,
            frame_duration=0.0,
            span_limits={"left": 9.75, "right": 10.25},
        )
        self.assertAlmostEqual(adjusted["duration"], 0.5)
        self.assertAlmostEqual(adjusted["position"], 9.75)
        self.assertAlmostEqual(adjusted["requested_duration"], 1.0)

    def test_build_transition_beat_marker_plan_marks_playhead_without_target(self):
        plan = build_transition_beat_marker_plan(
            None,
            "playhead",
            playhead_position=12.25,
            marker_positions=[],
            fallback_bpm=120.0,
        )
        self.assertEqual(plan["positions"], [12.25])
        self.assertAlmostEqual(plan["anchor_position"], 12.25)

    def test_build_transition_beat_marker_plan_creates_one_beat_window_around_cut(self):
        plan = build_transition_beat_marker_plan(
            {"enabled": True, "position": 10.0, "duration": 0.5},
            "beat_pair",
            playhead_position=0.0,
            marker_positions=[9.75, 10.25, 10.75],
            fallback_bpm=120.0,
        )
        self.assertEqual(plan["beat_info"]["source"], "markers")
        self.assertEqual(len(plan["positions"]), 2)
        self.assertAlmostEqual(plan["positions"][0], 9.75)
        self.assertAlmostEqual(plan["positions"][1], 10.75)

    def test_build_transition_beat_marker_plan_clear_nearby_includes_cut_and_pair(self):
        plan = build_transition_beat_marker_plan(
            {"enabled": True, "position": 20.0, "duration": 0.5},
            "clear_nearby",
            playhead_position=0.0,
            marker_positions=[],
            fallback_bpm=120.0,
        )
        self.assertEqual(len(plan["positions"]), 3)
        self.assertAlmostEqual(plan["positions"][1], 20.25)

    def test_find_transition_audio_transient_uses_strongest_nearby_waveform_hit(self):
        clips = [
            DummyItem(
                {
                    "position": 10.0,
                    "start": 0.0,
                    "end": 1.0,
                    "reader": {"has_audio": True, "has_video": False},
                    "ui": {"audio_data": [0.01, 0.02, 0.08, 0.82, 0.16, 0.05]},
                }
            )
        ]
        transient = find_transition_audio_transient(
            10.5,
            clips,
            marker_positions=[],
            fallback_bpm=120.0,
        )
        self.assertIsNotNone(transient)
        self.assertAlmostEqual(transient["position"], 10.6, places=2)

    def test_find_transition_audio_transient_returns_none_for_flat_silence(self):
        clips = [
            DummyItem(
                {
                    "position": 3.0,
                    "start": 0.0,
                    "end": 1.0,
                    "reader": {"has_audio": True, "has_video": False},
                    "ui": {"audio_data": [0.0, 0.0, 0.0, 0.0, 0.0]},
                }
            )
        ]
        transient = find_transition_audio_transient(
            3.5,
            clips,
            marker_positions=[],
            fallback_bpm=120.0,
        )
        self.assertIsNone(transient)

    def test_get_transition_transient_search_radius_tracks_beat_context(self):
        radius = get_transition_transient_search_radius(
            8.0,
            marker_positions=[7.5, 8.5],
            fallback_bpm=120.0,
        )
        self.assertGreaterEqual(radius, 0.12)
        self.assertLessEqual(radius, 0.45)

    def test_resolve_transition_overlap_span_matches_best_clip_pair(self):
        transition_data = {
            "layer": 2,
            "position": 5.8,
            "start": 0.0,
            "end": 0.4,
        }
        clips = [
            DummyItem({"layer": 2, "position": 4.0, "start": 0.0, "end": 2.2}),
            DummyItem({"layer": 2, "position": 5.6, "start": 0.0, "end": 1.5}),
            DummyItem({"layer": 1, "position": 5.6, "start": 0.0, "end": 1.5}),
        ]
        span = resolve_transition_overlap_span(transition_data, clips)
        self.assertIsNotNone(span)
        self.assertAlmostEqual(span["position"], 5.6)
        self.assertAlmostEqual(span["duration"], 0.6)

    def test_scale_transition_style_contrast_tracks_amount_levels(self):
        self.assertLess(
            scale_transition_style_contrast(5.0, "soft"),
            scale_transition_style_contrast(5.0, "default"),
        )
        self.assertLess(
            scale_transition_style_contrast(5.0, "default"),
            scale_transition_style_contrast(5.0, "hard"),
        )
