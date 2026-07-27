"""
ThemeCard widget for GtkFlowBox grid displaying theme thumbnail, title, author, score, and badge.
"""
import os
import threading
import logging
import httpx
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Adw, Gdk, GLib, Gio, GdkPixbuf, Pango

from motif.api.models import ThemeItem

logger = logging.getLogger(__name__)

# Image cache dict in memory
IMAGE_CACHE = {}

class ThumbnailPicture(Gtk.Picture):
    __gtype_name__ = "ThumbnailPicture"

    def do_measure(self, orientation, for_size):
        # min, natural, min-baseline, natural-baseline — hard-locked to 240x150 so size request ignores paintable resolution
        if orientation == Gtk.Orientation.HORIZONTAL:
            return (240, 240, -1, -1)
        return (150, 150, -1, -1)

class ThemeCard(Gtk.FlowBoxChild):
    def __init__(self, item: ThemeItem, on_favorite_toggled=None):
        super().__init__()
        self.item = item
        self.on_favorite_toggled = on_favorite_toggled

        self.set_valign(Gtk.Align.FILL)
        self.set_halign(Gtk.Align.FILL)
        self.add_css_class("theme-card")

        # Outer card container
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.add_css_class("card")
        card.add_css_class("theme-card")
        card.set_size_request(240, 250)
        card.set_valign(Gtk.Align.FILL)
        card.set_halign(Gtk.Align.FILL)

        # Image Container
        self.image_area = Gtk.Overlay()
        self.image_area.set_size_request(240, 150)
        self.image_area.set_overflow(Gtk.Overflow.HIDDEN)
        self.image_area.add_css_class("thumbnail-area")

        # Thumbnail picture explicitly constrained
        self.picture = ThumbnailPicture()
        self.picture.set_size_request(240, 150)
        self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.picture.set_can_shrink(True)
        self.picture.set_hexpand(False)
        
        # Fallback icon / placeholder
        self.placeholder = Gtk.Image.new_from_icon_name(self._get_fallback_icon(item.type_key))
        self.placeholder.set_pixel_size(48)
        self.placeholder.add_css_class("dim-label")
        self.placeholder.set_valign(Gtk.Align.CENTER)
        self.placeholder.set_halign(Gtk.Align.CENTER)

        # Loading Spinner for Thumbnail
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(28, 28)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_valign(Gtk.Align.CENTER)

        self.image_area.set_child(self.picture)
        self.image_area.add_overlay(self.placeholder)
        self.image_area.add_overlay(self.spinner)

        # Category Badge overlay (top-left)
        badge = Gtk.Label(label=item.type_key.upper())
        badge.add_css_class("pill")
        badge.add_css_class("caption-heading")
        badge.set_halign(Gtk.Align.START)
        badge.set_valign(Gtk.Align.START)
        badge.set_margin_top(8)
        badge.set_margin_start(8)
        self.image_area.add_overlay(badge)

        # Favorite Heart Button (top-right)
        self.fav_button = Gtk.Button()
        self.fav_button.add_css_class("flat")
        self.fav_button.add_css_class("circular")
        self.fav_button.set_halign(Gtk.Align.END)
        self.fav_button.set_valign(Gtk.Align.START)
        self.fav_button.set_margin_top(6)
        self.fav_button.set_margin_end(6)
        self._update_fav_icon()
        self.fav_button.connect("clicked", self._on_fav_clicked)
        self.image_area.add_overlay(self.fav_button)

        card.append(self.image_area)

        # Info Box
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_margin_start(12)
        info_box.set_margin_end(12)
        info_box.set_margin_top(10)
        info_box.set_margin_bottom(10)
        info_box.set_vexpand(True)

        # Title (Wrapping up to 2 lines to show full title)
        title_label = Gtk.Label(label=item.name)
        title_label.set_halign(Gtk.Align.START)
        title_label.add_css_class("heading")
        title_label.set_wrap(True)
        title_label.set_lines(2)
        title_label.set_ellipsize(PangoEllipsizeModeTruncate(title_label))
        title_label.set_tooltip_text(item.name)
        info_box.append(title_label)

        # Author
        author_label = Gtk.Label(label=f"by {item.author}")
        author_label.set_halign(Gtk.Align.START)
        author_label.add_css_class("caption")
        author_label.add_css_class("dim-label")
        author_label.set_wrap(True)
        author_label.set_lines(1)
        author_label.set_ellipsize(PangoEllipsizeModeTruncate(author_label))
        info_box.append(author_label)

        # Spacer to force stats to the bottom of the uniform card
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        info_box.append(spacer)

        # Stats row (Score & Downloads)
        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        score_label = Gtk.Label(label=f"Rating: {item.score}")
        score_label.add_css_class("caption")
        score_label.add_css_class("numeric")
        stats_box.append(score_label)

        dl_str = f"⬇ {item.downloads}"
        if item.downloads > 1000:
            dl_str = f"⬇ {item.downloads / 1000:.1f}k"
        dl_label = Gtk.Label(label=dl_str)
        dl_label.add_css_class("caption")
        dl_label.add_css_class("dim-label")
        stats_box.append(dl_label)

        info_box.append(stats_box)

        card.append(info_box)
        self.set_child(card)

        # Load image async
        if item.preview_urls:
            self._load_image_async(item.preview_urls[0])

    def _update_fav_icon(self):
        if self.item.is_favorite:
            self.fav_button.set_icon_name("starred-symbolic")
            self.fav_button.set_opacity(1.0)
            self.fav_button.add_css_class("accent")
            self.fav_button.remove_css_class("dim-label")
        else:
            self.fav_button.set_icon_name("non-starred-symbolic")
            self.fav_button.set_opacity(0.4)
            self.fav_button.remove_css_class("accent")
            self.fav_button.add_css_class("dim-label")

    def _on_fav_clicked(self, btn):
        if self.on_favorite_toggled:
            self.on_favorite_toggled(self.item)
        else:
            self.item.is_favorite = not self.item.is_favorite
        self._update_fav_icon()

    def _load_image_async(self, url: str):
        self.spinner.start()
        self.spinner.set_visible(True)

        if url in IMAGE_CACHE:
            self._set_picture_bytes(IMAGE_CACHE[url])
            return

        def fetch_worker():
            try:
                with httpx.Client(follow_redirects=True, timeout=8.0) as client:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        data = resp.content
                        IMAGE_CACHE[url] = data
                        GLib.idle_add(self._set_picture_bytes, data)
                    else:
                        GLib.idle_add(self._on_image_failed)
            except Exception as e:
                logger.debug(f"Failed loading thumbnail {url}: {e}")
                GLib.idle_add(self._on_image_failed)

        threading.Thread(target=fetch_worker, daemon=True).start()

    def _on_image_failed(self):
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.placeholder.set_visible(True)

    def _set_picture_bytes(self, data: bytes):
        try:
            glib_bytes = GLib.Bytes.new(data)
            texture = Gdk.Texture.new_from_bytes(glib_bytes)
            self.picture.set_paintable(texture)
            self.placeholder.set_visible(False)
        except Exception as e:
            logger.debug(f"Error setting texture: {e}")
            self.placeholder.set_visible(True)
        finally:
            self.spinner.stop()
            self.spinner.set_visible(False)

    @staticmethod
    def _get_fallback_icon(type_key: str) -> str:
        icons = {
            "gtk": "preferences-desktop-theme-symbolic",
            "shell": "preferences-system-windows-symbolic",
            "icon": "emblem-photos-symbolic",
            "cursor": "input-mouse-symbolic",
            "wallpaper": "preferences-desktop-wallpaper-symbolic"
        }
        return icons.get(type_key, "package-x-generic-symbolic")

def PangoEllipsizeModeTruncate(label: Gtk.Label):
    import gi
    gi.require_version("Pango", "1.0")
    from gi.repository import Pango
    return Pango.EllipsizeMode.END
