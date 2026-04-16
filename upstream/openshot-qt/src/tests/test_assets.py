"""
 @file
 @brief Unit tests for project asset path resolution
"""

import os
import sys
import unittest
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from classes.assets import get_assets_path


class AssetsPathTests(unittest.TestCase):
    def test_get_assets_path_uses_user_path_for_backup_project(self):
        with patch("classes.assets.info.USER_PATH", "/home/test/.openshot_qt"), \
             patch("classes.assets.info.BACKUP_FILE", "/home/test/.openshot_qt/backup.osp"), \
             patch("classes.assets.info.RECOVERY_PATH", "/home/test/.openshot_qt/recovery"):
            asset_path = get_assets_path("/home/test/.openshot_qt/backup.osp", create_paths=False)

        self.assertEqual(asset_path, "/home/test/.openshot_qt")

    def test_get_assets_path_uses_user_path_for_recovery_project(self):
        with patch("classes.assets.info.USER_PATH", "/home/test/.openshot_qt"), \
             patch("classes.assets.info.BACKUP_FILE", "/home/test/.openshot_qt/backup.osp"), \
             patch("classes.assets.info.RECOVERY_PATH", "/home/test/.openshot_qt/recovery"):
            asset_path = get_assets_path("/home/test/.openshot_qt/recovery/123/project.osp", create_paths=False)

        self.assertEqual(asset_path, "/home/test/.openshot_qt")
