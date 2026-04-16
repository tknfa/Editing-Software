"""
 @file
 @brief Unit tests for workspace cleanup helpers
"""

import os
import sys
import unittest


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from windows.views.workspace_cleanup import (
    WORKSPACE_MODE_DEFAULT,
    WORKSPACE_MODE_FULL,
    WORKSPACE_MODE_SIMPLE,
    WORKSPACE_MENU_SUPPRESSED_ACTIONS,
    normalize_workspace_mode,
    workspace_dock_plan,
    workspace_menu_labels,
)


class WorkspaceCleanupHelperTests(unittest.TestCase):
    def test_normalize_workspace_mode_defaults_to_simple(self):
        self.assertEqual(normalize_workspace_mode("mystery"), WORKSPACE_MODE_DEFAULT)
        self.assertEqual(normalize_workspace_mode(WORKSPACE_MODE_FULL), WORKSPACE_MODE_FULL)

    def test_workspace_dock_plan_for_simple_mode_hides_legacy_browser_docks(self):
        plan = workspace_dock_plan(WORKSPACE_MODE_SIMPLE)

        self.assertIn("dockFiles", plan["visible"])
        self.assertIn("dockProperties", plan["visible"])
        self.assertIn("dockTimeline", plan["visible"])
        self.assertIn("dockEffects", plan["hidden"])
        self.assertIn("dockTransitions", plan["hidden"])
        self.assertIn("dockEmojis", plan["hidden"])
        self.assertIn("dockTutorial", plan["hidden"])

    def test_workspace_dock_plan_for_full_mode_restores_edit_browser_docks(self):
        plan = workspace_dock_plan(WORKSPACE_MODE_FULL)

        self.assertIn("dockEffects", plan["visible"])
        self.assertIn("dockTransitions", plan["visible"])
        self.assertIn("dockEmojis", plan["visible"])
        self.assertNotIn("dockEffects", plan["hidden"])
        self.assertIn("dockTutorial", plan["hidden"])

    def test_workspace_menu_labels_match_quick_edit_language(self):
        labels = workspace_menu_labels(WORKSPACE_MODE_SIMPLE)

        self.assertEqual(labels["menu_title"], "Workspace")
        self.assertEqual(labels["simple_action"], "Quick Edit Workspace")
        self.assertEqual(labels["full_action"], "Full Workspace")
        self.assertEqual(labels["active_status"], "Quick Edit")
        self.assertIn("actionFreeze_View", WORKSPACE_MENU_SUPPRESSED_ACTIONS)


if __name__ == "__main__":
    unittest.main()
