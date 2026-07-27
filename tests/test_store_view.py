import unittest
from unittest.mock import MagicMock
import tempfile
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from motif.api.models import ThemeItem
from motif.core.favorites_manager import FavoritesManager
from motif.ui.store_view import StoreView, CATEGORIES, STYLE_OPTIONS


class TestStoreView(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.mock_ocs = MagicMock()
        self.mock_ocs.search_content.return_value = ([], 0)
        self.mock_scanner = MagicMock()
        self.mock_scanner.scan_all.return_value = []
        self.fav_mgr = FavoritesManager(config_dir=self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_store_view_initialization(self):
        view = StoreView(
            ocs_client=self.mock_ocs,
            favorites_mgr=self.fav_mgr,
            scanner=self.mock_scanner
        )
        self.assertIsInstance(view, Gtk.Box)
        self.assertEqual(view.bottom_loading_box.get_valign(), Gtk.Align.END)
        self.assertFalse(view.bottom_loading_box.get_visible())
        self.assertFalse(view.hide_installed)

    def test_item_passes_filters_style_and_hide_installed(self):
        view = StoreView(
            ocs_client=self.mock_ocs,
            favorites_mgr=self.fav_mgr,
            scanner=self.mock_scanner
        )
        
        dark_item = ThemeItem(
            id="1", name="Orchis Dark", author="a", version="1", summary="Dark GTK theme",
            description="", changelog="", category_id="1", category_name="GTK", type_key="gtk",
            score=10, downloads=100, created=""
        )
        light_item = ThemeItem(
            id="2", name="Adwaita Light", author="a", version="1", summary="Light theme",
            description="", changelog="", category_id="1", category_name="GTK", type_key="gtk",
            score=10, downloads=100, created=""
        )

        # 1. Dark style filter
        view.current_style = "dark"
        self.assertTrue(view._item_passes_filters(dark_item))
        self.assertFalse(view._item_passes_filters(light_item))

        # 2. Light style filter
        view.current_style = "light"
        self.assertFalse(view._item_passes_filters(dark_item))
        self.assertTrue(view._item_passes_filters(light_item))

        # 3. Hide installed filter with dashes/underscores
        view.current_style = "all"
        view.hide_installed = True
        view._installed_names_cache = {"orchis-dark"}
        self.assertFalse(view._item_passes_filters(dark_item))
        self.assertTrue(view._item_passes_filters(light_item))

    def test_sort_options_has_relevance(self):
        from motif.ui.store_view import SORT_OPTIONS
        keys = [k for k, _ in SORT_OPTIONS]
        self.assertIn("relevance", keys)


if __name__ == "__main__":
    unittest.main()
