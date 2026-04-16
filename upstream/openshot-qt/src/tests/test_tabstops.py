"""
 @file
 @brief Unit tests for tab-order helpers
"""

import os
import sys
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDockWidget, QLineEdit, QMainWindow, QVBoxLayout, QWidget


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from classes.tabstops import apply_auto_tab_order, apply_explicit_tab_order


_APP = QApplication.instance() or QApplication([])


class TabOrderHelperTests(unittest.TestCase):
    def test_apply_explicit_tab_order_skips_cross_window_pairs(self):
        first_window = QWidget()
        second_window = QWidget()
        first = QLineEdit(first_window)
        foreign = QLineEdit(second_window)
        third = QLineEdit(first_window)

        calls = []
        with patch("classes.tabstops.QWidget.setTabOrder", side_effect=lambda a, b: calls.append((a, b))):
            apply_explicit_tab_order(
                [first, foreign, third],
                root=first_window,
                include_hidden=True,
                include_disabled=True,
            )

        self.assertEqual(calls, [(first, third)])

    def test_apply_auto_tab_order_ignores_floating_dock_widgets_for_main_window(self):
        window = QMainWindow()
        central = QWidget(window)
        layout = QVBoxLayout(central)
        main_first = QLineEdit(central)
        main_second = QLineEdit(central)
        layout.addWidget(main_first)
        layout.addWidget(main_second)
        window.setCentralWidget(central)

        floating_dock = QDockWidget("Floating", window)
        floating_content = QWidget(floating_dock)
        floating_layout = QVBoxLayout(floating_content)
        floating_input = QLineEdit(floating_content)
        floating_layout.addWidget(floating_input)
        floating_dock.setWidget(floating_content)
        window.addDockWidget(Qt.LeftDockWidgetArea, floating_dock)
        floating_dock.setFloating(True)

        window.show()
        floating_dock.show()
        _APP.processEvents()

        calls = []
        with patch("classes.tabstops.QWidget.setTabOrder", side_effect=lambda a, b: calls.append((a, b))):
            apply_auto_tab_order(window, include_hidden=True, include_disabled=True)

        self.assertTrue(calls)
        self.assertTrue(all(first.window() is second.window() for first, second in calls))
        self.assertFalse(any(first is floating_input or second is floating_input for first, second in calls))

        floating_dock.close()
        window.close()


if __name__ == "__main__":
    unittest.main()
