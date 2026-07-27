import unittest
from unittest.mock import MagicMock
import tempfile
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk

from motif.api.models import ThemeItem
from motif.ui.author_view import AuthorView
from motif.ui.widgets.author_card import AuthorCard


class TestAuthorView(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.mock_ocs = MagicMock()
        self.mock_ocs.search_content.return_value = ([], 0)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_author_card_widget(self):
        card = AuthorCard(
            author_name="vinceliuice",
            theme_count=12,
            sample_titles=["Orchis GTK", "WhiteSur GTK"]
        )
        self.assertIsInstance(card, Gtk.FlowBoxChild)
        self.assertEqual(card.author_name, "vinceliuice")

    def test_author_view_initialization(self):
        view = AuthorView(ocs_client=self.mock_ocs)
        self.assertIsInstance(view, Gtk.Box)
        view.set_author("vinceliuice")
        self.assertEqual(view.author_name, "vinceliuice")


if __name__ == "__main__":
    unittest.main()
