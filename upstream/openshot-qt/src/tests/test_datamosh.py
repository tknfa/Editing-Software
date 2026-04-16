"""
 @file
 @brief Unit tests for datamosh helpers
"""

import os
import sys
import unittest
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from classes import ui_text
from classes.datamosh_service import (
    DATAMOSH_AMOUNT_UI_KEY,
    DATAMOSH_HISTORY_ID_UI_KEY,
    DATAMOSH_PRESET_UI_KEY,
    DatamoshService,
    build_datamosh_cache_key,
    build_datamosh_history_entry,
    build_datamosh_output_path,
    build_datamosh_render_project,
    build_datamosh_render_settings,
    build_datamosh_render_signature,
    build_datamosh_temp_output_path,
    clip_visible_duration_seconds,
    datamosh_render_frame_range,
    get_persisted_datamosh_amount_key,
    get_persisted_datamosh_history,
    get_persisted_datamosh_source_clip_id,
    merge_datamosh_history,
    resolve_datamosh_clip_target,
    set_persisted_datamosh_generated_metadata,
    set_persisted_datamosh_history,
)


class DummyClip:
    def __init__(self, data, title="Clip"):
        self.data = data
        self._title = title

    def title(self):
        return self._title


class DummyStoredClip(DummyClip):
    def __init__(self, clip_id, data, title="Clip"):
        super().__init__(data, title=title)
        self.id = clip_id
        self.save_calls = 0

    def save(self):
        self.save_calls += 1


class DatamoshHelperTests(unittest.TestCase):
    def test_clip_visible_duration_seconds_uses_trimmed_span(self):
        self.assertAlmostEqual(
            clip_visible_duration_seconds({"start": 2.0, "end": 3.75, "duration": 4.0}),
            1.75,
        )

    def test_build_datamosh_cache_key_changes_when_trim_changes(self):
        clip_a = {"start": 0.0, "end": 2.0}
        clip_b = {"start": 0.5, "end": 2.0}
        key_a = build_datamosh_cache_key("/tmp/source.mp4", clip_a, "cut_mosh", 1.0)
        key_b = build_datamosh_cache_key("/tmp/source.mp4", clip_b, "cut_mosh", 1.0)
        self.assertNotEqual(key_a, key_b)

    def test_build_datamosh_cache_key_changes_when_effect_stack_changes(self):
        clip_a = {"start": 0.0, "end": 2.0, "effects": []}
        clip_b = {"start": 0.0, "end": 2.0, "effects": [{"name": "Wave"}]}
        key_a = build_datamosh_cache_key("/tmp/source.mp4", clip_a, "cut_mosh", 1.0)
        key_b = build_datamosh_cache_key("/tmp/source.mp4", clip_b, "cut_mosh", 1.0)
        self.assertNotEqual(key_a, key_b)

    def test_build_datamosh_cache_key_changes_when_amount_changes(self):
        clip_data = {"start": 0.0, "end": 2.0}
        key_default = build_datamosh_cache_key(
            "/tmp/source.mp4",
            clip_data,
            "cut_mosh",
            1.0,
            amount_key="default",
        )
        key_wild = build_datamosh_cache_key(
            "/tmp/source.mp4",
            clip_data,
            "cut_mosh",
            1.0,
            amount_key="wild",
        )
        self.assertNotEqual(key_default, key_wild)

    def test_build_datamosh_render_signature_ignores_datamosh_ui_only(self):
        base_clip = {
            "start": 0.0,
            "end": 2.0,
            "ui": {
                "datamosh_history": [{"id": "cached"}],
                "datamosh_source_clip_id": "clip-source",
                "datamosh_history_id": "cached",
                "datamosh_preset_key": "cut_mosh",
                "datamosh_amount_key": "wild",
                "effect_card_preset": "jugg_shake",
            },
        }
        signature = build_datamosh_render_signature(base_clip)
        self.assertEqual(signature["ui"], {"effect_card_preset": "jugg_shake"})

        cache_a = build_datamosh_cache_key("/tmp/source.mp4", base_clip, "cut_mosh", 1.0)
        mutated = {
            "start": 0.0,
            "end": 2.0,
            "ui": {
                "datamosh_history": [{"id": "other"}],
                "datamosh_source_clip_id": "clip-other",
                "datamosh_history_id": "other",
                "datamosh_preset_key": "classic_melt",
                "datamosh_amount_key": "light",
                "effect_card_preset": "jugg_shake",
            },
        }
        cache_b = build_datamosh_cache_key("/tmp/source.mp4", mutated, "cut_mosh", 1.0)
        self.assertEqual(cache_a, cache_b)

    def test_build_datamosh_output_path_uses_clean_name(self):
        path = build_datamosh_output_path("/tmp/datamosh", "My Clip!!", "repeat_melt", "abcdef123456")
        self.assertEqual(path, "/tmp/datamosh/my-clip-repeat-melt-abcdef1234.mp4")

    def test_build_datamosh_output_path_includes_amount_slug_for_non_default_variants(self):
        path = build_datamosh_output_path(
            "/tmp/datamosh",
            "My Clip!!",
            "repeat_melt",
            "abcdef123456",
            amount_key="wild",
        )
        self.assertEqual(path, "/tmp/datamosh/my-clip-repeat-melt-wild-abcdef1234.mp4")

    def test_build_datamosh_temp_output_path_preserves_media_extension(self):
        self.assertEqual(
            build_datamosh_temp_output_path("/tmp/datamosh/output.mp4"),
            "/tmp/datamosh/output.tmp.mp4",
        )

    def test_resolve_datamosh_clip_target_accepts_single_video_clip(self):
        clip = DummyClip(
            {
                "start": 0.0,
                "end": 2.0,
                "reader": {"path": __file__, "has_video": True, "has_single_image": False},
            },
            title="Main Take",
        )
        target = resolve_datamosh_clip_target(
            [{"id": "clip-1", "type": "clip"}],
            clip_lookup=lambda clip_id: clip if clip_id == "clip-1" else None,
        )
        self.assertTrue(target["enabled"])
        self.assertEqual(target["clip_id"], "clip-1")
        self.assertIn("Main Take", target["summary"])

    def test_resolve_datamosh_clip_target_sanitizes_emoji_title_on_macos(self):
        clip = DummyClip(
            {
                "start": 0.0,
                "end": 2.0,
                "reader": {"path": __file__, "has_video": True, "has_single_image": False},
            },
            title="Main Take 🤯",
        )
        with patch.object(ui_text.platform, "system", return_value="Darwin"):
            target = resolve_datamosh_clip_target(
                [{"id": "clip-1", "type": "clip"}],
                clip_lookup=lambda clip_id: clip if clip_id == "clip-1" else None,
            )

        self.assertTrue(target["enabled"])
        self.assertIn("Main Take ?", target["summary"])
        self.assertNotIn("🤯", target["summary"])

    def test_build_datamosh_render_project_isolates_selected_clip(self):
        project_data = {
            "clips": [
                {"id": "clip-1", "layer": 3, "position": 5.0, "effects": [{"name": "Glow"}]},
                {"id": "clip-2", "layer": 4, "position": 8.0},
            ],
            "effects": [{"id": "tran-1", "layer": 3}],
            "markers": [{"id": "marker-1"}],
            "layers": [
                {"number": 3, "label": "Video 1"},
                {"number": 4, "label": "Video 2"},
            ],
            "files": [{"id": "file-1", "path": "/tmp/source.mp4"}],
        }

        render_project = build_datamosh_render_project(project_data, project_data["clips"][0])
        self.assertEqual([clip["id"] for clip in render_project["clips"]], ["clip-1"])
        self.assertEqual(render_project["effects"], [])
        self.assertEqual(render_project["markers"], [])
        self.assertEqual(render_project["history"], {"undo": [], "redo": []})
        self.assertEqual([layer["number"] for layer in render_project["layers"]], [3])
        self.assertEqual(render_project["files"], project_data["files"])

    def test_build_datamosh_render_settings_uses_project_profile_defaults(self):
        settings = build_datamosh_render_settings(
            {
                "width": 1920,
                "height": 1080,
                "fps": {"num": 24000, "den": 1001},
                "pixel_ratio": {"num": 1, "den": 1},
                "sample_rate": 44100,
                "channels": 2,
                "channel_layout": 3,
            }
        )
        self.assertEqual(settings["width"], 1920)
        self.assertEqual(settings["height"], 1080)
        self.assertEqual(settings["fps"], {"num": 24000, "den": 1001})
        self.assertEqual(settings["sample_rate"], 44100)
        self.assertEqual(settings["channels"], 2)
        self.assertEqual(settings["channel_layout"], 3)

    def test_datamosh_render_frame_range_uses_clip_position_and_duration(self):
        start_frame, end_frame = datamosh_render_frame_range(
            {"position": 5.0, "start": 0.0, "end": 2.0},
            {"fps": {"num": 24, "den": 1}},
        )
        self.assertEqual(start_frame, 121)
        self.assertEqual(end_frame, 168)

    def test_resolve_datamosh_clip_target_rejects_audio_only_clip(self):
        clip = DummyClip(
            {
                "start": 0.0,
                "end": 2.0,
                "reader": {"path": __file__, "has_video": False, "has_audio": True},
            }
        )
        target = resolve_datamosh_clip_target(
            [{"id": "clip-1", "type": "clip"}],
            clip_lookup=lambda _clip_id: clip,
        )
        self.assertFalse(target["enabled"])
        self.assertIn("video clip", target["message"])

    def test_build_datamosh_history_entry_keeps_recent_variant_metadata(self):
        entry = build_datamosh_history_entry(
            "classic_melt",
            "/tmp/cache/clip-classic-melt-1234567890.mp4",
            "Main Take",
            amount_key="wild",
            generated_clip_id="clip-9",
            file_id="file-2",
            track_number=4,
            position=12.5,
        )
        self.assertEqual(entry["preset_key"], "classic_melt")
        self.assertEqual(entry["preset_label"], "Classic Melt")
        self.assertEqual(entry["amount_key"], "wild")
        self.assertEqual(entry["amount_label"], "Wild")
        self.assertEqual(entry["generated_clip_id"], "clip-9")
        self.assertEqual(entry["track_number"], 4)
        self.assertAlmostEqual(entry["position"], 12.5)

    def test_merge_datamosh_history_moves_existing_entry_to_front_and_trims(self):
        entries = [
            {"id": "a.mp4", "output_path": "/tmp/a.mp4"},
            {"id": "b.mp4", "output_path": "/tmp/b.mp4"},
            {"id": "c.mp4", "output_path": "/tmp/c.mp4"},
        ]
        merged = merge_datamosh_history(
            entries,
            {"id": "b.mp4", "output_path": "/tmp/b.mp4", "preset_key": "repeat_melt"},
            limit=2,
        )
        self.assertEqual([entry["id"] for entry in merged], ["b.mp4", "a.mp4"])

    def test_persisted_datamosh_history_round_trips_on_clip_ui(self):
        clip_data = {}
        entry = build_datamosh_history_entry(
            "repeat_melt",
            "/tmp/cache/main-repeat-melt-1234567890.mp4",
            "Main Take",
            generated_clip_id="clip-generated",
        )
        self.assertTrue(set_persisted_datamosh_history(clip_data, [entry]))

        persisted = get_persisted_datamosh_history(clip_data)
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0]["id"], entry["id"])
        self.assertEqual(persisted[0]["generated_clip_id"], "clip-generated")

        persisted[0]["generated_clip_id"] = "mutated"
        self.assertEqual(
            get_persisted_datamosh_history(clip_data)[0]["generated_clip_id"],
            "clip-generated",
        )

    def test_persisted_generated_metadata_round_trips_on_clip_ui(self):
        clip_data = {}
        entry = build_datamosh_history_entry(
            "classic_melt",
            "/tmp/cache/main-classic-melt-1234567890.mp4",
            "Main Take",
        )

        self.assertTrue(set_persisted_datamosh_generated_metadata(clip_data, "clip-source", entry))
        self.assertEqual(get_persisted_datamosh_source_clip_id(clip_data), "clip-source")
        self.assertEqual(get_persisted_datamosh_amount_key(clip_data), "default")
        self.assertEqual(clip_data["ui"][DATAMOSH_HISTORY_ID_UI_KEY], entry["id"])
        self.assertEqual(clip_data["ui"][DATAMOSH_PRESET_UI_KEY], "classic_melt")
        self.assertEqual(clip_data["ui"][DATAMOSH_AMOUNT_UI_KEY], "default")

    def test_service_remember_history_persists_source_and_generated_clip_metadata(self):
        source_clip = DummyStoredClip("clip-source", {"reader": {"path": __file__}}, title="Main Take")
        generated_clip = DummyStoredClip("clip-generated", {"reader": {"path": __file__}}, title="Main Take - Melt")
        clip_map = {
            source_clip.id: source_clip,
            generated_clip.id: generated_clip,
        }
        entry = build_datamosh_history_entry(
            "jiggle_pulse",
            "/tmp/cache/main-jiggle-pulse-1234567890.mp4",
            "Main Take",
            generated_clip_id=generated_clip.id,
        )

        service = DatamoshService(None)
        with patch("classes.datamosh_service.Clip.get", side_effect=lambda id=None, **_kwargs: clip_map.get(id)):
            merged = service._remember_history_entry(source_clip.id, entry)

        self.assertEqual(len(merged), 1)
        self.assertEqual(source_clip.save_calls, 1)
        self.assertEqual(generated_clip.save_calls, 1)
        self.assertEqual(get_persisted_datamosh_history(source_clip.data)[0]["id"], entry["id"])
        self.assertEqual(get_persisted_datamosh_source_clip_id(generated_clip.data), source_clip.id)

    def test_service_hydrates_history_from_persisted_source_clip_metadata(self):
        entry = build_datamosh_history_entry(
            "cut_mosh",
            "/tmp/cache/main-cut-mosh-1234567890.mp4",
            "Main Take",
            generated_clip_id="clip-generated",
        )
        source_clip = DummyStoredClip("clip-source", {}, title="Main Take")
        set_persisted_datamosh_history(source_clip.data, [entry])
        generated_clip = DummyStoredClip("clip-generated", {}, title="Main Take - Cut Mosh")
        set_persisted_datamosh_generated_metadata(generated_clip.data, source_clip.id, entry)
        clip_map = {
            source_clip.id: source_clip,
            generated_clip.id: generated_clip,
        }

        service = DatamoshService(None)
        with patch("classes.datamosh_service.Clip.get", side_effect=lambda id=None, **_kwargs: clip_map.get(id)):
            self.assertEqual(service.resolve_history_source_clip_id(generated_clip.id), source_clip.id)
            history = service.get_clip_history(generated_clip.id)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["preset_key"], "cut_mosh")
        self.assertEqual(history[0]["generated_clip_id"], generated_clip.id)
        self.assertEqual(history[0]["amount_key"], "default")
