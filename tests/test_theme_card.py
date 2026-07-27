import unittest
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, GdkPixbuf

from motif.ui.widgets.theme_card import ThemeCard, ThumbnailPicture
from motif.api.models import ThemeItem


class TestThemeCard(unittest.TestCase):
    def setUp(self):
        self.item = ThemeItem(
            id="1",
            name="Test Theme",
            category_id="gtk",
            category_name="GTK Theme",
            type_key="gtk",
            version="1.0",
            summary="A test theme",
            description="Full test description",
            changelog="Initial release",
            created="2026-01-01",
            author="Developer",
            score=9,
            downloads=5000,
            preview_urls=[]
        )

    def test_thumbnail_picture_measure(self):
        pic = ThumbnailPicture()
        h_req = pic.do_measure(Gtk.Orientation.HORIZONTAL, -1)
        v_req = pic.do_measure(Gtk.Orientation.VERTICAL, -1)

        self.assertEqual(h_req, (240, 240, -1, -1))
        self.assertEqual(v_req, (150, 150, -1, -1))

    def test_theme_card_creation(self):
        card = ThemeCard(self.item)
        self.assertIsInstance(card.picture, ThumbnailPicture)

    def test_set_picture_bytes_downscales(self):
        card = ThemeCard(self.item)
        pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 800, 600)
        success, buffer = pb.save_to_bufferv("png", [], [])
        self.assertTrue(success)

        card._set_picture_bytes(buffer)
        self.assertFalse(card.placeholder.get_visible())

    def test_favorite_icon_toggle(self):
        self.item.is_favorite = False
        card = ThemeCard(self.item)
        self.assertEqual(card.fav_button.get_icon_name(), "non-starred-symbolic")

        card.fav_button.emit("clicked")
        self.assertTrue(self.item.is_favorite)
        self.assertEqual(card.fav_button.get_icon_name(), "starred-symbolic")

        card.fav_button.emit("clicked")
        self.assertFalse(self.item.is_favorite)
        self.assertEqual(card.fav_button.get_icon_name(), "non-starred-symbolic")


if __name__ == "__main__":
    unittest.main()
