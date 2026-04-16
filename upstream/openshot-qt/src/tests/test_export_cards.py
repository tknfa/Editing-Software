"""
 @file
 @brief Unit tests for compact export preset helpers
"""

import os
import sys
import unittest
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from windows.views.export_cards import (
    EXPORT_CARD_DEFAULT_KEY,
    apply_export_card_preset,
    build_export_card_filename,
    build_export_card_summary,
    choose_export_card_target_title,
    normalize_export_card_preset_key,
)


class FakeCombo:
    def __init__(self, items):
        self._items = list(items)
        self._current_index = 0

    def count(self):
        return len(self._items)

    def itemText(self, index):
        return self._items[index][0]

    def itemData(self, index):
        return self._items[index][1]

    def setCurrentIndex(self, index):
        self._current_index = int(index)

    def currentIndex(self):
        return self._current_index


class FakeLineEdit:
    def __init__(self, text=""):
        self._text = str(text)

    def setText(self, text):
        self._text = str(text)

    def text(self):
        return self._text


class FakeButton:
    def __init__(self):
        self._text = ""
        self.focused = False

    def setText(self, text):
        self._text = str(text)

    def text(self):
        return self._text

    def setFocus(self):
        self.focused = True


class FakeTabs:
    def __init__(self):
        self.current_index = None

    def setCurrentIndex(self, index):
        self.current_index = int(index)


class FakeDialog:
    def __init__(self):
        self.exportTabs = FakeTabs()
        self.cboSimpleProjectType = FakeCombo([
            ("All Formats", "All Formats"),
        ])
        self.cboSimpleTarget = FakeCombo([
            ("MP4 (h.264 videotoolbox)", "MP4 (h.264 videotoolbox)"),
            ("MP4 (h.264)", "MP4 (h.264)"),
            ("MP4 (h.264) lossless", "MP4 (h.264) lossless"),
            ("MP3 (audio only)", "MP3 (audio only)"),
        ])
        self.cboSimpleQuality = FakeCombo([
            ("Low", "Low"),
            ("Med", "Med"),
            ("High", "High"),
        ])
        self.txtFileName = FakeLineEdit("")
        self.txtExportFolder = FakeLineEdit("")
        self.export_button = FakeButton()
        self.tab_order_applied = False

    def _apply_tab_order(self):
        self.tab_order_applied = True


class FakeSettings:
    class actionType:
        EXPORT = "export"

    def getDefaultPath(self, _action):
        return "/tmp/exports"


class FakeProject:
    current_filepath = "/tmp/Personal Cut.osp"


class FakeApp:
    def __init__(self):
        self.project = FakeProject()
        self._settings = FakeSettings()
        self._tr = lambda text: text

    def get_settings(self):
        return self._settings


class ExportCardHelperTests(unittest.TestCase):
    def test_normalize_export_card_preset_key_defaults_cleanly(self):
        self.assertEqual(normalize_export_card_preset_key("mystery"), EXPORT_CARD_DEFAULT_KEY)
        self.assertEqual(normalize_export_card_preset_key("audio_mp3"), "audio_mp3")

    def test_build_export_card_filename_adds_suffix_for_specialized_presets(self):
        self.assertEqual(
            build_export_card_filename("/tmp/Edit.osp", "lossless_mp4"),
            "Edit master",
        )
        self.assertEqual(
            build_export_card_filename("", "audio_mp3"),
            "Untitled Project audio",
        )

    def test_choose_export_card_target_title_prefers_first_available_match(self):
        self.assertEqual(
            choose_export_card_target_title(
                ["MP4 (h.264)", "MP4 (h.264 videotoolbox)"],
                ["MP4 (h.264 videotoolbox)", "MP4 (h.264)"],
            ),
            "MP4 (h.264 videotoolbox)",
        )
        self.assertEqual(
            choose_export_card_target_title(
                ["MP4 (h.264)"],
                ["MP4 (h.264) lossless", "MP4 (h.264)"],
            ),
            "MP4 (h.264)",
        )

    def test_build_export_card_summary_surfaces_project_and_folder(self):
        summary = build_export_card_summary("/tmp/Edit.osp", "/tmp/exports")

        self.assertIn('Ready to export "Edit"', summary["headline"])
        self.assertIn("/tmp/exports", summary["detail"])

    def test_apply_export_card_preset_prefills_dialog_for_quick_mp4(self):
        dialog = FakeDialog()
        app = FakeApp()

        with patch("windows.views.export_cards.get_app", return_value=app):
            result = apply_export_card_preset(dialog, "quick_mp4")

        self.assertEqual(dialog.exportTabs.current_index, 0)
        self.assertEqual(dialog.cboSimpleTarget.currentIndex(), 0)
        self.assertEqual(dialog.cboSimpleQuality.currentIndex(), 1)
        self.assertEqual(dialog.txtFileName.text(), "Personal Cut")
        self.assertEqual(dialog.txtExportFolder.text(), "/tmp/exports")
        self.assertEqual(dialog.export_button.text(), "Export Quick MP4")
        self.assertTrue(dialog.export_button.focused)
        self.assertTrue(dialog.tab_order_applied)
        self.assertEqual(result["target_title"], "MP4 (h.264 videotoolbox)")

    def test_apply_export_card_preset_falls_back_when_lossless_target_missing(self):
        dialog = FakeDialog()
        dialog.cboSimpleTarget = FakeCombo([
            ("MP4 (h.264)", "MP4 (h.264)"),
            ("MP3 (audio only)", "MP3 (audio only)"),
        ])
        app = FakeApp()

        with patch("windows.views.export_cards.get_app", return_value=app):
            result = apply_export_card_preset(dialog, "lossless_mp4")

        self.assertEqual(dialog.cboSimpleTarget.currentIndex(), 0)
        self.assertEqual(dialog.cboSimpleQuality.currentIndex(), 2)
        self.assertEqual(dialog.txtFileName.text(), "Personal Cut master")
        self.assertEqual(result["target_title"], "MP4 (h.264)")


if __name__ == "__main__":
    unittest.main()
