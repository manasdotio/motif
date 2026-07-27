import unittest
from unittest.mock import MagicMock, patch
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from motif.window import MotifWindow


class TestMotifWindow(unittest.TestCase):
    @patch("motif.window.ThemeScanner")
    @patch("motif.window.OCSClient")
    def test_window_actions_and_github_link(self, mock_ocs, mock_scanner):
        window = MotifWindow()
        self.assertIsInstance(window, Adw.ApplicationWindow)
        
        # Verify open_github action exists
        has_github_action = window.has_action("open_github")
        self.assertTrue(has_github_action)

        # Verify import_theme action exists
        has_import_action = window.has_action("import_theme")
        self.assertTrue(has_import_action)


if __name__ == "__main__":
    unittest.main()
