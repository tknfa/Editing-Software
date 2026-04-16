"""
 @file
 @brief Unit tests for clip look-card helpers
"""

import copy
import os
import sys
import unittest
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from classes import ui_text
from windows.views.effect_cards import (
    apply_clip_effect_card_preset,
    clear_clip_effect_card_preset,
    get_clip_effect_card_amount_key,
    get_clip_effect_card_preset_key,
    resolve_effect_card_target,
)


class DummyClip:
    def __init__(self, data, title="Clip"):
        self.data = data
        self._title = title

    def title(self):
        return self._title


def _id_generator():
    counter = {"value": 0}

    def generate():
        counter["value"] += 1
        return f"effect-{counter['value']}"

    return generate


class EffectCardHelperTests(unittest.TestCase):
    def test_resolve_target_accepts_visual_clips(self):
        clips = {
            "clip-a": DummyClip(
                {
                    "reader": {"has_video": True, "has_single_image": False},
                    "start": 0.0,
                    "end": 2.0,
                },
                title="Hero Shot",
            ),
            "clip-b": DummyClip(
                {
                    "reader": {"has_video": True, "has_single_image": False},
                    "start": 0.0,
                    "end": 1.0,
                },
                title="Cutaway",
            ),
        }

        target = resolve_effect_card_target(
            [
                {"id": "clip-a", "type": "clip"},
                {"id": "clip-b", "type": "clip"},
            ],
            clip_lookup=lambda clip_id: clips.get(clip_id),
        )

        self.assertTrue(target["enabled"])
        self.assertEqual(target["clip_ids"], ["clip-a", "clip-b"])
        self.assertIn("selected clips", target["summary"])

    def test_resolve_target_sanitizes_emoji_title_on_macos(self):
        clip = DummyClip(
            {
                "reader": {"has_video": True, "has_single_image": False},
                "start": 0.0,
                "end": 2.0,
            },
            title="Hero Shot 🤯",
        )

        with patch.object(ui_text.platform, "system", return_value="Darwin"):
            target = resolve_effect_card_target(
                [{"id": "clip-a", "type": "clip"}],
                clip_lookup=lambda _clip_id: clip,
            )

        self.assertTrue(target["enabled"])
        self.assertIn("Hero Shot ?", target["summary"])
        self.assertNotIn("🤯", target["summary"])

    def test_resolve_target_rejects_audio_only_clip(self):
        clip = DummyClip(
            {
                "reader": {"has_video": False, "has_audio": True},
                "start": 0.0,
                "end": 2.0,
            }
        )
        target = resolve_effect_card_target(
            [{"id": "clip-a", "type": "clip"}],
            clip_lookup=lambda _clip_id: clip,
        )

        self.assertFalse(target["enabled"])
        self.assertIn("visible image or video", target["message"])

    def test_apply_punch_zoom_sets_backup_and_managed_effects(self):
        clip_data = {
            "reader": {"has_video": True, "has_single_image": False},
            "start": 0.0,
            "end": 2.0,
            "scale_x": {"Points": [{"co": {"X": 1, "Y": 1.0}, "interpolation": 1}]},
            "scale_y": {"Points": [{"co": {"X": 1, "Y": 1.0}, "interpolation": 1}]},
        }

        changed = apply_clip_effect_card_preset(clip_data, 24.0, "punch_zoom", _id_generator())

        self.assertTrue(changed)
        self.assertEqual(get_clip_effect_card_preset_key(clip_data), "punch_zoom")
        self.assertEqual(get_clip_effect_card_amount_key(clip_data), "default")
        self.assertIn("effect_card_backup", clip_data["ui"])
        self.assertGreater(clip_data["scale_x"]["Points"][0]["co"]["Y"], 1.0)
        managed_names = [effect.get("class_name") for effect in clip_data.get("effects", [])]
        self.assertEqual(managed_names, ["Blur", "Brightness"])

    def test_swapping_presets_replaces_only_managed_effects(self):
        clip_data = {
            "reader": {"has_video": True, "has_single_image": False},
            "start": 0.0,
            "end": 2.0,
            "effects": [
                {
                    "id": "existing-1",
                    "class_name": "Pixelate",
                    "ui": {"icon_color": "#fff"},
                }
            ],
        }

        generate_id = _id_generator()
        self.assertTrue(apply_clip_effect_card_preset(clip_data, 24.0, "rgb_split", generate_id))
        self.assertTrue(apply_clip_effect_card_preset(clip_data, 24.0, "glitch_ripple", generate_id))

        self.assertEqual(get_clip_effect_card_preset_key(clip_data), "glitch_ripple")
        effect_names = [effect.get("class_name") for effect in clip_data.get("effects", [])]
        self.assertEqual(effect_names, ["Pixelate", "Wave", "ColorShift"])

    def test_clear_restores_original_transform_and_keeps_user_effects(self):
        original_scale = {"Points": [{"co": {"X": 1, "Y": 1.33}, "interpolation": 1}]}
        clip_data = {
            "reader": {"has_video": True, "has_single_image": False},
            "start": 0.0,
            "end": 1.5,
            "scale_x": copy.deepcopy(original_scale),
            "scale_y": copy.deepcopy(original_scale),
            "effects": [
                {
                    "id": "existing-1",
                    "class_name": "Pixelate",
                    "ui": {"icon_color": "#fff"},
                }
            ],
        }

        generate_id = _id_generator()
        self.assertTrue(apply_clip_effect_card_preset(clip_data, 24.0, "punch_zoom", generate_id))
        self.assertTrue(clear_clip_effect_card_preset(clip_data))

        self.assertEqual(clip_data["scale_x"], original_scale)
        self.assertEqual(clip_data["scale_y"], original_scale)
        self.assertEqual([effect.get("class_name") for effect in clip_data.get("effects", [])], ["Pixelate"])
        self.assertIsNone(get_clip_effect_card_preset_key(clip_data))
        self.assertIsNone(get_clip_effect_card_amount_key(clip_data))
        self.assertNotIn("effect_card_backup", clip_data.get("ui", {}))

    def test_apply_punch_zoom_hard_amount_is_stronger_than_soft(self):
        soft_clip = {
            "reader": {"has_video": True, "has_single_image": False},
            "start": 0.0,
            "end": 2.0,
        }
        hard_clip = copy.deepcopy(soft_clip)
        generate_id = _id_generator()

        self.assertTrue(
            apply_clip_effect_card_preset(
                soft_clip,
                24.0,
                "punch_zoom",
                generate_id,
                amount_key="soft",
            )
        )
        self.assertTrue(
            apply_clip_effect_card_preset(
                hard_clip,
                24.0,
                "punch_zoom",
                generate_id,
                amount_key="hard",
            )
        )

        self.assertEqual(get_clip_effect_card_amount_key(soft_clip), "soft")
        self.assertEqual(get_clip_effect_card_amount_key(hard_clip), "hard")
        self.assertLess(
            soft_clip["scale_x"]["Points"][0]["co"]["Y"],
            hard_clip["scale_x"]["Points"][0]["co"]["Y"],
        )


if __name__ == "__main__":
    unittest.main()
