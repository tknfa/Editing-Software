"""
 @file
 @brief Focused tests for properties tableview helpers
"""

import importlib
import os
import sys
import unittest
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)


properties_tableview = importlib.import_module("windows.views.properties_tableview")
ui_text = importlib.import_module("classes.ui_text")


class PropertiesTableViewHelperTests(unittest.TestCase):
    def test_sanitize_button_text_replaces_non_bmp_emoji_on_macos(self):
        with patch.object(ui_text.platform, "system", return_value="Darwin"):
            self.assertEqual(
                properties_tableview._sanitize_button_text("FLYING KNEE 🤯"),
                "FLYING KNEE ?",
            )

    def test_sanitize_button_text_preserves_text_off_macos(self):
        with patch.object(ui_text.platform, "system", return_value="Linux"):
            self.assertEqual(
                properties_tableview._sanitize_button_text("FLYING KNEE 🤯"),
                "FLYING KNEE 🤯",
            )


if __name__ == "__main__":
    unittest.main()
