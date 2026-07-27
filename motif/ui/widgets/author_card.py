"""
AuthorCard widget for GtkFlowBox grid displaying author avatar picture, handle, package count, and action button.
"""
import threading
import logging
import httpx
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Adw, Gdk, GLib, Pango

from motif.ui.widgets.theme_card import IMAGE_CACHE

logger = logging.getLogger(__name__)

class AuthorCard(Gtk.FlowBoxChild):
    def __init__(self, author_name: str, theme_count: int, sample_titles: list[str], on_author_clicked=None):
        super().__init__()
        self.author_name = author_name
        self.on_author_clicked = on_author_clicked

        self.set_valign(Gtk.Align.FILL)
        self.set_halign(Gtk.Align.FILL)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("card")
        card.set_size_request(240, 250)
        card.set_margin_start(4)
        card.set_margin_end(4)
        card.set_margin_top(4)
        card.set_margin_bottom(4)

        # Header area with Avatar Overlay
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header_box.set_margin_top(16)
        header_box.set_halign(Gtk.Align.CENTER)

        self.avatar_box = Gtk.Overlay()
        self.avatar_box.set_size_request(54, 54)
        self.avatar_box.set_overflow(Gtk.Overflow.HIDDEN)

        self.avatar_picture = Gtk.Picture()
        self.avatar_picture.set_content_fit(Gtk.ContentFit.COVER)
        self.avatar_picture.set_size_request(54, 54)
        self.avatar_picture.add_css_class("circular")
        self.avatar_box.set_child(self.avatar_picture)

        self.avatar_fallback = Gtk.Image.new_from_icon_name("avatar-default-symbolic")
        self.avatar_fallback.set_pixel_size(54)
        self.avatar_fallback.add_css_class("accent")
        self.avatar_box.add_overlay(self.avatar_fallback)

        header_box.append(self.avatar_box)

        name_label = Gtk.Label(label=f"@{author_name}")
        name_label.add_css_class("title-3")
        name_label.set_halign(Gtk.Align.CENTER)
        name_label.set_wrap(True)
        name_label.set_lines(1)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        header_box.append(name_label)

        count_badge = Gtk.Label(label=f"{theme_count} theme{'s' if theme_count != 1 else ''}")
        count_badge.add_css_class("pill")
        count_badge.add_css_class("caption")
        count_badge.set_halign(Gtk.Align.CENTER)
        header_box.append(count_badge)

        card.append(header_box)

        # Sample titles preview box
        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        preview_box.set_margin_start(12)
        preview_box.set_margin_end(12)
        preview_box.set_vexpand(True)

        for title in sample_titles[:2]:
            t_lbl = Gtk.Label(label=f"• {title}")
            t_lbl.add_css_class("caption")
            t_lbl.add_css_class("dim-label")
            t_lbl.set_halign(Gtk.Align.START)
            t_lbl.set_wrap(True)
            t_lbl.set_lines(1)
            t_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            preview_box.append(t_lbl)

        card.append(preview_box)

        # View Profile Action Button
        btn = Gtk.Button(label="View Profile →")
        btn.add_css_class("pill")
        btn.add_css_class("flat")
        btn.add_css_class("accent")
        btn.set_margin_start(12)
        btn.set_margin_end(12)
        btn.set_margin_bottom(12)
        btn.connect("clicked", lambda b: self._on_clicked())
        card.append(btn)

        self.set_child(card)

        # Load avatar picture async
        self._load_avatar_async()

    def _load_avatar_async(self):
        avatar_url = f"https://www.opendesktop.org/avatar/{self.author_name}"
        if avatar_url in IMAGE_CACHE:
            self._set_picture_bytes(IMAGE_CACHE[avatar_url])
            return

        def fetch_worker():
            try:
                with httpx.Client(follow_redirects=True, timeout=8.0) as client:
                    resp = client.get(avatar_url)
                    if resp.status_code == 200:
                        data = resp.content
                        IMAGE_CACHE[avatar_url] = data
                        GLib.idle_add(self._set_picture_bytes, data)
            except Exception as e:
                logger.debug(f"Failed loading avatar for card {self.author_name}: {e}")

        threading.Thread(target=fetch_worker, daemon=True).start()

    def _set_picture_bytes(self, data: bytes):
        try:
            glib_bytes = GLib.Bytes.new(data)
            texture = Gdk.Texture.new_from_bytes(glib_bytes)
            self.avatar_picture.set_paintable(texture)
            self.avatar_fallback.set_visible(False)
        except Exception as e:
            logger.debug(f"Error setting avatar texture: {e}")

    def _on_clicked(self):
        if self.on_author_clicked:
            self.on_author_clicked(self.author_name)
