import unittest
from unittest.mock import MagicMock
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from motif.ui.installed_view import InstalledView
from motif.api.models import InstalledTheme


class TestInstalledView(unittest.TestCase):
    def setUp(self):
        self.mock_scanner = MagicMock()
        self.mock_gsettings = MagicMock()

        self.mock_gsettings.get_active_themes.return_value = {
            "gtk": "Adwaita",
            "shell": "Default",
            "icon": "Adwaita",
            "cursor": "Adwaita",
            "wallpaper": ""
        }
        self.mock_gsettings.is_user_themes_extension_enabled.return_value = True
        self.mock_gsettings.is_xcursor_path_configured.return_value = True

        self.mock_scanner.scan_all.return_value = [
            InstalledTheme(
                name="Test-Theme",
                type_key="gtk",
                path="/home/user/.themes/Test-Theme",
                is_active=True,
                is_motif_managed=True
            )
        ]

    def test_installed_view_preferences_page(self):
        view = InstalledView(
            scanner=self.mock_scanner,
            gsettings_mgr=self.mock_gsettings
        )

        self.assertIsInstance(view, Adw.PreferencesPage)
        self.assertGreater(len(view._groups), 0)

    def test_refresh_installed_clears_and_repopulates(self):
        view = InstalledView(
            scanner=self.mock_scanner,
            gsettings_mgr=self.mock_gsettings
        )
        initial_count = len(view._groups)

        view.refresh_installed()
        self.assertEqual(len(view._groups), initial_count)

    def test_perform_delete_calls_safe_remove_path(self):
        view = InstalledView(
            scanner=self.mock_scanner,
            gsettings_mgr=self.mock_gsettings,
            on_toast=MagicMock()
        )
        theme = InstalledTheme(
            name="Test-Theme",
            type_key="gtk",
            path="/home/user/.themes/Test-Theme",
            is_active=True,
            is_motif_managed=True
        )

        with unittest.mock.patch("motif.ui.installed_view.safe_remove_path") as mock_remove:
            view._perform_delete(theme)
            self.mock_gsettings.revert_to_default.assert_called_once_with("gtk")
            mock_remove.assert_called_once_with("/home/user/.themes/Test-Theme")
            view.on_toast.assert_called_with("Deleted 'Test-Theme' cleanly.")


if __name__ == "__main__":
    unittest.main()
