"""
 @file
 @brief Unit tests for custom retime helpers
"""

import os
import sys
import unittest

from PyQt5.QtWidgets import QApplication

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

_APP = QApplication.instance() or QApplication([])

from windows.views.retime import (
    SpeedGraphDialog,
    apply_clip_retime_audio_behavior,
    apply_clip_retime_interpolation_mode,
    apply_speed_graph_segment,
    apply_time_segment_easing,
    calculate_custom_retime_metrics,
    get_active_speed_graph_segment,
    get_clip_playhead_frame,
    get_clip_average_speed,
    get_clip_duration_seconds,
    get_clip_retime_audio_summary,
    get_clip_retime_interpolation_key,
    get_clip_retime_interpolation_summary,
    get_time_curve_preview_segments,
    get_time_curve_playhead_summary,
    get_clip_retime_summary,
    get_clip_time_direction,
    normalize_property_filter_token,
    remove_time_point,
    upsert_time_point,
)


class RetimeHelperTests(unittest.TestCase):
    def test_get_clip_duration_seconds_snaps_to_frames(self):
        clip_data = {"start": 1.0, "end": 3.49, "duration": 2.49}
        self.assertAlmostEqual(get_clip_duration_seconds(clip_data, 24.0), 60 / 24.0)

    def test_get_clip_time_direction_detects_reverse_curve(self):
        clip_data = {
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 120}},
                    {"co": {"X": 120, "Y": 1}},
                ]
            }
        }
        self.assertEqual(get_clip_time_direction(clip_data), -1)

    def test_calculate_custom_retime_metrics_speed_mode_scales_current_duration(self):
        clip_data = {"start": 2.0, "end": 6.0, "duration": 4.0}
        metrics = calculate_custom_retime_metrics(clip_data, 30.0, "speed", 2.0)
        self.assertIsNotNone(metrics)
        self.assertAlmostEqual(metrics["current_duration"], 4.0)
        self.assertAlmostEqual(metrics["new_duration"], 2.0)
        self.assertAlmostEqual(metrics["new_end"], 4.0)
        self.assertAlmostEqual(metrics["relative_speed"], 2.0)

    def test_calculate_custom_retime_metrics_duration_mode_snaps_target_duration(self):
        clip_data = {"start": 0.5, "end": 5.5, "duration": 5.0}
        metrics = calculate_custom_retime_metrics(clip_data, 24.0, "duration", 1.2)
        self.assertIsNotNone(metrics)
        self.assertAlmostEqual(metrics["current_duration"], 5.0)
        self.assertAlmostEqual(metrics["new_duration"], 29 / 24.0)
        self.assertAlmostEqual(metrics["new_end"], 0.5 + (29 / 24.0))
        self.assertAlmostEqual(metrics["relative_speed"], 5.0 / (29 / 24.0))

    def test_get_clip_average_speed_uses_time_curve_span(self):
        clip_data = {
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}},
                    {"co": {"X": 121, "Y": 241}},
                ]
            },
        }
        self.assertAlmostEqual(get_clip_average_speed(clip_data, 30.0), 2.0)

    def test_get_clip_retime_summary_detects_ramp_curve(self):
        clip_data = {
            "start": 0.0,
            "end": 3.0,
            "duration": 3.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}},
                    {"co": {"X": 46, "Y": 30}},
                    {"co": {"X": 91, "Y": 121}},
                ]
            },
        }
        summary = get_clip_retime_summary(clip_data, 30.0)
        self.assertTrue(summary["has_ramp"])
        self.assertEqual(summary["direction"], 1)
        self.assertEqual(summary["curve_points"], 3)

    def test_upsert_time_point_inserts_sorted_ramp_point(self):
        clip_data = {
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}, "interpolation": 1},
                    {"co": {"X": 121, "Y": 121}, "interpolation": 1},
                ]
            },
        }
        changed, point = upsert_time_point(clip_data, 30.0, 61, 75)
        self.assertTrue(changed)
        self.assertEqual(point["co"]["X"], 61)
        self.assertEqual(
            [entry["co"]["X"] for entry in clip_data["time"]["Points"]],
            [1, 61, 121],
        )

    def test_remove_time_point_keeps_endpoints(self):
        clip_data = {
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}, "interpolation": 1},
                    {"co": {"X": 61, "Y": 75}, "interpolation": 1},
                    {"co": {"X": 121, "Y": 121}, "interpolation": 1},
                ]
            },
        }
        self.assertTrue(remove_time_point(clip_data, 30.0, 61))
        self.assertEqual(
            [entry["co"]["X"] for entry in clip_data["time"]["Points"]],
            [1, 121],
        )
        self.assertFalse(remove_time_point(clip_data, 30.0, 1))

    def test_apply_time_segment_easing_updates_handles(self):
        clip_data = {
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}, "interpolation": 1},
                    {"co": {"X": 61, "Y": 75}, "interpolation": 1},
                    {"co": {"X": 121, "Y": 121}, "interpolation": 1},
                ]
            },
        }
        self.assertTrue(apply_time_segment_easing(clip_data, 30.0, 50, "ease_in_out"))
        mid_point = clip_data["time"]["Points"][1]
        start_point = clip_data["time"]["Points"][0]
        self.assertEqual(mid_point["interpolation"], 0)
        self.assertEqual(start_point["handle_right"], {"X": 0.42, "Y": 0.0})
        self.assertEqual(mid_point["handle_left"], {"X": 0.58, "Y": 1.0})

    def test_get_clip_playhead_frame_clamps_to_interior(self):
        clip_data = {
            "position": 10.0,
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}, "interpolation": 1},
                    {"co": {"X": 121, "Y": 121}, "interpolation": 1},
                ]
            },
        }
        self.assertEqual(get_clip_playhead_frame(clip_data, 30.0, 10.0, interior=True), 2)
        self.assertEqual(get_clip_playhead_frame(clip_data, 30.0, 14.0, interior=True), 120)

    def test_normalize_property_filter_token_maps_time_aliases(self):
        self.assertEqual(normalize_property_filter_token("Time"), "time")
        self.assertEqual(normalize_property_filter_token("time curve"), "time")
        self.assertEqual(normalize_property_filter_token("location x"), "location_x")

    def test_get_time_curve_preview_segments_detects_reverse_span(self):
        clip_data = {
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 121}, "interpolation": 1},
                    {"co": {"X": 121, "Y": 1}, "interpolation": 1},
                ]
            },
        }
        segments = get_time_curve_preview_segments(clip_data, 30.0)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["kind"], "reverse")
        self.assertAlmostEqual(segments[0]["start_ratio"], 0.0)
        self.assertAlmostEqual(segments[0]["end_ratio"], 1.0)

    def test_get_time_curve_preview_segments_detects_hold_and_freeze(self):
        clip_data = {
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}, "interpolation": 1},
                    {"co": {"X": 41, "Y": 1}, "interpolation": 1},
                    {"co": {"X": 81, "Y": 60}, "interpolation": 2},
                    {"co": {"X": 121, "Y": 121}, "interpolation": 1},
                ]
            },
        }
        segments = get_time_curve_preview_segments(clip_data, 30.0)
        self.assertEqual([segment["kind"] for segment in segments], ["freeze", "hold"])
        self.assertEqual(segments[0]["label"], "Freeze")
        self.assertEqual(segments[1]["label"], "Hold")

    def test_get_time_curve_playhead_summary_reports_reverse_segment(self):
        clip_data = {
            "position": 0.0,
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 121}, "interpolation": 1},
                    {"co": {"X": 121, "Y": 1}, "interpolation": 1},
                ]
            },
        }
        summary = get_time_curve_playhead_summary(clip_data, 30.0, 2.0)
        self.assertEqual(summary["segment_kind"], "reverse")
        self.assertEqual(summary["easing_label"], "Linear")
        self.assertIn("Reverse", summary["segment_label"])
        self.assertTrue(summary["source_label"].startswith("F"))

    def test_get_time_curve_playhead_summary_reports_hold_easing(self):
        clip_data = {
            "position": 0.0,
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}, "interpolation": 1},
                    {"co": {"X": 61, "Y": 1}, "interpolation": 2},
                    {"co": {"X": 121, "Y": 121}, "interpolation": 1},
                ]
            },
        }
        summary = get_time_curve_playhead_summary(clip_data, 30.0, 1.0)
        self.assertEqual(summary["segment_kind"], "hold")
        self.assertEqual(summary["easing_label"], "Hold")
        self.assertEqual(summary["segment_label"], "Hold")

    def test_get_active_speed_graph_segment_uses_interior_pair(self):
        clip_data = {
            "position": 0.0,
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}, "interpolation": 1},
                    {"co": {"X": 31, "Y": 31}, "interpolation": 1},
                    {"co": {"X": 91, "Y": 121}, "interpolation": 1},
                    {"co": {"X": 121, "Y": 151}, "interpolation": 1},
                ]
            },
        }
        segment = get_active_speed_graph_segment(clip_data, 30.0, 2.0)
        self.assertIsNotNone(segment)
        self.assertEqual(segment["start_frame"], 31)
        self.assertEqual(segment["end_frame"], 91)
        self.assertEqual(segment["control_points"], [{"x": 0.0, "speed": 1.0}, {"x": 1.0, "speed": 1.0}])

    def test_apply_speed_graph_segment_creates_metadata_and_managed_points(self):
        clip_data = {
            "position": 0.0,
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}, "interpolation": 1},
                    {"co": {"X": 31, "Y": 31}, "interpolation": 1},
                    {"co": {"X": 91, "Y": 121}, "interpolation": 1},
                    {"co": {"X": 121, "Y": 151}, "interpolation": 1},
                ]
            },
        }
        segment = get_active_speed_graph_segment(clip_data, 30.0, 2.0)
        changed = apply_speed_graph_segment(
            clip_data,
            30.0,
            segment,
            [{"x": 0.0, "speed": 0.5}, {"x": 0.4, "speed": 2.0}, {"x": 1.0, "speed": 0.5}],
            curve_mode="expo_in_out",
        )
        self.assertTrue(changed)
        self.assertIn("ui", clip_data)
        self.assertIn("speed_graph_segments", clip_data["ui"])
        self.assertEqual(len(clip_data["ui"]["speed_graph_segments"]), 1)
        self.assertEqual(clip_data["ui"]["speed_graph_segments"][0]["curve_mode"], "expo_in_out")
        managed_points = [
            point
            for point in clip_data["time"]["Points"]
            if point.get("ui_speed_graph_managed")
        ]
        self.assertGreater(len(managed_points), 0)
        segment_after = get_active_speed_graph_segment(clip_data, 30.0, 2.0)
        self.assertTrue(segment_after["managed"])
        self.assertEqual(len(segment_after["control_points"]), 3)
        self.assertEqual(segment_after["curve_mode"], "expo_in_out")

    def test_apply_speed_graph_segment_fast_span_shortens_clip_duration(self):
        clip_data = {
            "position": 0.0,
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}, "interpolation": 1},
                    {"co": {"X": 31, "Y": 31}, "interpolation": 1},
                    {"co": {"X": 91, "Y": 121}, "interpolation": 1},
                    {"co": {"X": 121, "Y": 151}, "interpolation": 1},
                ]
            },
        }

        segment = get_active_speed_graph_segment(clip_data, 30.0, 2.0)
        changed = apply_speed_graph_segment(
            clip_data,
            30.0,
            segment,
            [{"x": 0.0, "speed": 2.0}, {"x": 1.0, "speed": 2.0}],
        )

        self.assertTrue(changed)
        self.assertAlmostEqual(clip_data["duration"], 3.0)
        self.assertAlmostEqual(clip_data["end"], 3.0)
        frames = [point["co"]["X"] for point in clip_data["time"]["Points"]]
        self.assertEqual(frames[0], 1)
        self.assertEqual(frames[1], 31)
        self.assertEqual(frames[-2], 61)
        self.assertEqual(frames[-1], 91)

    def test_apply_speed_graph_segment_slow_span_lengthens_clip_duration(self):
        clip_data = {
            "position": 0.0,
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}, "interpolation": 1},
                    {"co": {"X": 31, "Y": 31}, "interpolation": 1},
                    {"co": {"X": 91, "Y": 121}, "interpolation": 1},
                    {"co": {"X": 121, "Y": 151}, "interpolation": 1},
                ]
            },
        }

        segment = get_active_speed_graph_segment(clip_data, 30.0, 2.0)
        changed = apply_speed_graph_segment(
            clip_data,
            30.0,
            segment,
            [{"x": 0.0, "speed": 0.5}, {"x": 1.0, "speed": 0.5}],
        )

        self.assertTrue(changed)
        self.assertAlmostEqual(clip_data["duration"], 6.0)
        self.assertAlmostEqual(clip_data["end"], 6.0)
        frames = [point["co"]["X"] for point in clip_data["time"]["Points"]]
        self.assertEqual(frames[0], 1)
        self.assertEqual(frames[1], 31)
        self.assertEqual(frames[-2], 151)
        self.assertEqual(frames[-1], 181)

    def test_apply_speed_graph_segment_reset_clears_metadata(self):
        clip_data = {
            "position": 0.0,
            "start": 0.0,
            "end": 4.0,
            "duration": 4.0,
            "time": {
                "Points": [
                    {"co": {"X": 1, "Y": 1}, "interpolation": 1},
                    {"co": {"X": 31, "Y": 31}, "interpolation": 1},
                    {"co": {"X": 91, "Y": 121}, "interpolation": 1},
                    {"co": {"X": 121, "Y": 151}, "interpolation": 1},
                ]
            },
        }
        segment = get_active_speed_graph_segment(clip_data, 30.0, 2.0)
        apply_speed_graph_segment(
            clip_data,
            30.0,
            segment,
            [{"x": 0.0, "speed": 0.5}, {"x": 0.4, "speed": 2.0}, {"x": 1.0, "speed": 0.5}],
        )
        managed_segment = get_active_speed_graph_segment(clip_data, 30.0, 2.0)
        changed = apply_speed_graph_segment(
            clip_data,
            30.0,
            managed_segment,
            [{"x": 0.0, "speed": 1.0}, {"x": 1.0, "speed": 1.0}],
        )
        self.assertTrue(changed)
        self.assertNotIn("ui", clip_data)
        self.assertAlmostEqual(clip_data["duration"], 3.6)
        self.assertEqual(
            [point["co"]["X"] for point in clip_data["time"]["Points"]],
            [1, 31, 79, 109],
        )

    def test_speed_graph_dialog_exponential_mode_uses_valid_curve_preset(self):
        dialog = SpeedGraphDialog(
            {
                "segment_label": "Frames 31-91",
                "speed_label": "1.000x",
                "curve_mode": "linear",
            }
        )
        dialog._set_curve_family("exponential")
        self.assertEqual(dialog.curve_mode(), "expo_in_out")

    def test_get_clip_retime_audio_summary_reflects_audio_override(self):
        clip_data = {
            "reader": {"has_audio": True, "has_video": True},
            "has_audio": {
                "Points": [
                    {"co": {"X": 1, "Y": 0.0}, "interpolation": 2},
                ]
            },
            "ui": {"retime_audio_behavior": "mute"},
        }
        summary = get_clip_retime_audio_summary(clip_data)
        self.assertEqual(summary["audio_behavior_key"], "mute")
        self.assertEqual(summary["audio_label"], "Muted")
        self.assertEqual(summary["pitch_label"], "Muted")
        self.assertTrue(summary["has_audio_source"])
        self.assertTrue(summary["has_video_source"])

    def test_get_clip_retime_interpolation_defaults_to_optical_flow(self):
        clip_data = {"reader": {"has_video": True, "has_audio": True}}
        self.assertEqual(get_clip_retime_interpolation_key(clip_data), "optical_flow")
        summary = get_clip_retime_interpolation_summary(clip_data)
        self.assertEqual(summary["interpolation_label"], "Optical Flow")

    def test_apply_clip_retime_interpolation_mode_updates_clip_data(self):
        clip_data = {"reader": {"has_video": True, "has_audio": False}}
        changed = apply_clip_retime_interpolation_mode(clip_data, "frame_blend")
        self.assertTrue(changed)
        self.assertEqual(clip_data["time_interpolation"], 1)

    def test_get_clip_retime_audio_summary_reports_no_audio_source(self):
        clip_data = {"reader": {"has_audio": False, "has_video": True}}
        summary = get_clip_retime_audio_summary(clip_data)
        self.assertEqual(summary["audio_behavior_key"], "none")
        self.assertEqual(summary["audio_label"], "No audio")
        self.assertEqual(summary["pitch_label"], "N/A")
        self.assertFalse(summary["has_audio_source"])

    def test_apply_clip_retime_audio_behavior_sets_has_audio_override(self):
        clip_data = {"reader": {"has_audio": True, "has_video": False}, "ui": {}}
        changed = apply_clip_retime_audio_behavior(clip_data, "pitch_shift")
        self.assertTrue(changed)
        self.assertEqual(clip_data["ui"]["retime_audio_behavior"], "pitch_shift")
        self.assertEqual(clip_data["has_audio"]["Points"][0]["co"]["Y"], 1.0)

    def test_apply_clip_retime_audio_behavior_restores_source_default_label(self):
        clip_data = {
            "reader": {"has_audio": True, "has_video": False},
            "has_audio": {
                "Points": [
                    {"co": {"X": 1, "Y": 0.0}, "interpolation": 2},
                ]
            },
            "ui": {"retime_audio_behavior": "mute"},
        }
        changed = apply_clip_retime_audio_behavior(clip_data, "source_default")
        self.assertTrue(changed)
        self.assertNotIn("retime_audio_behavior", clip_data["ui"])
        self.assertEqual(clip_data["has_audio"]["Points"][0]["co"]["Y"], -1.0)

    def test_apply_clip_retime_audio_behavior_ignores_silent_sources(self):
        clip_data = {"reader": {"has_audio": False, "has_video": True}}
        changed = apply_clip_retime_audio_behavior(clip_data, "mute")
        self.assertFalse(changed)
        self.assertNotIn("has_audio", clip_data)


if __name__ == "__main__":
    unittest.main()
