"""
Detail view: displays full theme screenshots carousel, metadata, description, changelog, download files, and install action.
Structured with Adw.ToolbarView, Adw.Clamp, Adw.Carousel, Adw.ComboRow, and Adw.ViewStack.
"""
import os
import re
import html
import threading
import logging
from typing import Optional, List, Dict
import httpx
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Adw, Gdk, GLib, Gio, Pango

from motif.api.models import ThemeItem, DownloadFile
from motif.api.ocs_client import OCSClient
from motif.core.installer import ThemeInstaller, InstallationError
from motif.core.favorites_manager import FavoritesManager
from motif.core.gsettings_manager import GSettingsManager
from motif.ui.widgets.theme_card import IMAGE_CACHE, ThemeCard

logger = logging.getLogger(__name__)

def format_relative_time(date_str: str) -> str:
    """Calculates human-readable relative time string (e.g. '3 years ago', '2 days ago')."""
    if not date_str or not date_str.strip():
        return "recently"
    try:
        from datetime import datetime, timezone
        dt_str = date_str.strip()
        now = datetime.now(timezone.utc)
        if 'T' in dt_str:
            clean_str = re.sub(r'[\+\-]\d\d:\d\d$', '', dt_str).rstrip('Z')
            dt = datetime.fromisoformat(clean_str).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.strptime(dt_str[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc)
            
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 0:
            return "recently"
        
        minutes = seconds / 60
        hours = minutes / 60
        days = hours / 24
        months = days / 30.4375
        years = days / 365.25
        
        if years >= 1.0:
            y = int(years)
            return f"{y} year{'s' if y != 1 else ''} ago"
        elif months >= 1.0:
            m = int(months)
            return f"{m} month{'s' if m != 1 else ''} ago"
        elif days >= 1.0:
            d = int(days)
            return f"{d} day{'s' if d != 1 else ''} ago"
        elif hours >= 1.0:
            h = int(hours)
            return f"{h} hour{'s' if h != 1 else ''} ago"
        elif minutes >= 1.0:
            m = int(minutes)
            return f"{m} minute{'s' if m != 1 else ''} ago"
        else:
            return "just now"
    except Exception:
        return date_str

def format_version(ver: str) -> str:
    """Formats version string (e.g. 'version v0.4.1')."""
    v = (ver or "1.0").strip()
    if v.lower().startswith("v"):
        return f"version {v}"
    return f"version v{v}"

def sanitize_text(raw_text: str) -> str:
    """Strips HTML, raw markdown decorative artifacts, and collapses whitespace."""
    if not raw_text:
        return ""
    
    # 1. Replace line break tags before stripping HTML
    text = re.sub(r'<br\s*/?>', '\n', raw_text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    
    # 2. Strip decorative punctuation runs (e.g., "------", "======")
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if re.fullmatch(r'[-=*~_#\s]{3,}', line):
            continue
        line = re.sub(r'^[-=*~_#\s]{3,}', '', line)
        line = re.sub(r'[-=*~_#\s]{3,}$', '', line)
        lines.append(line.strip())
    
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

class DetailView(Gtk.Box):
    def __init__(
        self,
        ocs_client: OCSClient,
        installer: ThemeInstaller,
        favorites_mgr: Optional[FavoritesManager] = None,
        gsettings_mgr: Optional[GSettingsManager] = None,
        on_back_clicked=None,
        on_author_clicked=None,
        on_installed_toast=None
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.ocs_client = ocs_client
        self.installer = installer
        self.favorites_mgr = favorites_mgr
        self.gsettings_mgr = gsettings_mgr
        self.on_back_clicked = on_back_clicked
        self.on_author_clicked = on_author_clicked
        self.on_installed_toast = on_installed_toast
        
        self.item: Optional[ThemeItem] = None
        self.preview_textures: List[Gdk.Texture] = []

        # Adw.ToolbarView layout container
        self.toolbar_view = Adw.ToolbarView()
        self.toolbar_view.set_vexpand(True)
        self.toolbar_view.set_hexpand(True)

        # Header Bar
        self.header_bar = Adw.HeaderBar()
        
        back_btn = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        back_btn.set_tooltip_text("Back to Store")
        back_btn.connect("clicked", lambda b: self._on_back())
        self.header_bar.pack_start(back_btn)

        self.title_heading = Gtk.Label(label="Theme Details")
        self.title_heading.add_css_class("title-2")
        self.title_heading.set_halign(Gtk.Align.START)
        self.header_bar.set_title_widget(self.title_heading)

        self.fav_top_btn = Gtk.Button()
        self.fav_top_btn.add_css_class("flat")
        self.fav_top_btn.add_css_class("circular")
        self.fav_top_btn.set_tooltip_text("Toggle Favorite")
        self.fav_top_btn.connect("clicked", self._on_fav_top_clicked)
        self.header_bar.pack_end(self.fav_top_btn)

        self.toolbar_view.add_top_bar(self.header_bar)

        # Main Content inside Adw.Clamp
        clamp = Adw.Clamp()
        clamp.set_maximum_size(1050)
        clamp.set_tightening_threshold(850)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(24)

        # 1. Screenshot Gallery Overlay with Adw.Carousel, Indicator Dots & Side Navigation Controls
        self.carousel_overlay = Gtk.Overlay()
        self.carousel_overlay.set_size_request(-1, 380)
        self.carousel_overlay.set_overflow(Gtk.Overflow.HIDDEN)
        self.carousel_overlay.add_css_class("card")

        self.carousel = Adw.Carousel()
        self.carousel.set_size_request(-1, 380)

        # Attach scroll controllers to allow vertical page scrolling without trapping scroll events
        v_scroll_ctrl = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        v_scroll_ctrl.connect("scroll", lambda ctrl, dx, dy: False)
        self.carousel.add_controller(v_scroll_ctrl)

        h_scroll_ctrl = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.HORIZONTAL)
        h_scroll_ctrl.connect("scroll", self._on_carousel_h_scroll)
        self.carousel.add_controller(h_scroll_ctrl)

        self.carousel_overlay.set_child(self.carousel)

        # Indicator dots overlaid at bottom edge
        self.dots = Adw.CarouselIndicatorDots()
        self.dots.set_carousel(self.carousel)
        self.dots.set_valign(Gtk.Align.END)
        self.dots.set_margin_bottom(12)
        self.dots.add_css_class("osd")
        self.dots.add_css_class("pill")
        self.dots.set_visible(False)
        self.carousel_overlay.add_overlay(self.dots)

        # Fullscreen Zoom Button (top-right)
        self.nav_fullscreen = Gtk.Button.new_from_icon_name("view-fullscreen-symbolic")
        self.nav_fullscreen.add_css_class("osd")
        self.nav_fullscreen.add_css_class("circular")
        self.nav_fullscreen.set_size_request(40, 40)
        self.nav_fullscreen.set_halign(Gtk.Align.END)
        self.nav_fullscreen.set_valign(Gtk.Align.START)
        self.nav_fullscreen.set_margin_end(16)
        self.nav_fullscreen.set_margin_top(16)
        self.nav_fullscreen.set_tooltip_text("Open Fullscreen Preview")
        self.nav_fullscreen.set_visible(False)
        self.nav_fullscreen.connect("clicked", lambda b: self._open_fullscreen_preview())
        self.carousel_overlay.add_overlay(self.nav_fullscreen)

        self.gallery_spinner = Gtk.Spinner()
        self.gallery_spinner.set_size_request(32, 32)
        self.gallery_spinner.set_halign(Gtk.Align.CENTER)
        self.gallery_spinner.set_valign(Gtk.Align.CENTER)
        self.carousel_overlay.add_overlay(self.gallery_spinner)

        content.append(self.carousel_overlay)

        # 2. Title & Primary Action Row
        title_action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        self.name_label = Gtk.Label()
        self.name_label.add_css_class("title-1")
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.set_wrap(True)
        self.name_label.set_hexpand(True)
        self.name_label.set_xalign(0)
        title_action_row.append(self.name_label)

        action_btns_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_btns_box.set_valign(Gtk.Align.CENTER)
        action_btns_box.set_halign(Gtk.Align.END)

        self.install_btn = Gtk.Button(label="Install Theme")
        self.install_btn.add_css_class("suggested-action")
        self.install_btn.add_css_class("pill")
        self.install_btn.connect("clicked", self._on_install_clicked)
        action_btns_box.append(self.install_btn)

        self.apply_btn = Gtk.Button(label="Apply Theme Now")
        self.apply_btn.add_css_class("accent")
        self.apply_btn.add_css_class("pill")
        self.apply_btn.set_visible(False)
        self.apply_btn.connect("clicked", self._on_apply_clicked)
        action_btns_box.append(self.apply_btn)

        title_action_row.append(action_btns_box)
        content.append(title_action_row)

        # Progress indicator row
        self.progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_visible(False)
        self.progress_box.append(self.progress_bar)

        self.progress_label = Gtk.Label()
        self.progress_label.add_css_class("caption")
        self.progress_label.set_halign(Gtk.Align.START)
        self.progress_label.set_visible(False)
        self.progress_box.append(self.progress_label)
        content.append(self.progress_box)

        # 3. Links Section (GitHub/Source Code, Store Page, Homepage) placed ON TOP of stats
        links_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        links_box.set_halign(Gtk.Align.START)

        self.source_btn = Gtk.LinkButton.new_with_label("", "")
        self.source_btn.set_visible(False)
        links_box.append(self.source_btn)

        self.store_link_btn = Gtk.LinkButton.new_with_label("", "")
        self.store_link_btn.set_visible(False)
        links_box.append(self.store_link_btn)

        self.homepage_btn = Gtk.LinkButton.new_with_label("", "")
        self.homepage_btn.set_visible(False)
        links_box.append(self.homepage_btn)

        self.links_scroll = Gtk.ScrolledWindow()
        self.links_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.links_scroll.set_child(links_box)
        self.links_scroll.set_visible(False)
        content.append(self.links_scroll)

        # 4. Clean Scannable Metadata Row (author, rating, downloads, version, date) placed BELOW links
        meta_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        meta_row.set_halign(Gtk.Align.START)

        # Author Badge Button with Adw.Avatar
        self.author_btn = Gtk.Button()
        self.author_btn.add_css_class("pill")
        self.author_btn.add_css_class("flat")
        self.author_btn.set_tooltip_text("View creator profile")
        self.author_btn.connect("clicked", self._on_author_btn_clicked)

        author_child_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.author_avatar = Adw.Avatar.new(24, "Author", True)
        author_child_box.append(self.author_avatar)

        self.author_label = Gtk.Label(label="Author")
        author_child_box.append(self.author_label)

        self.author_btn.set_child(author_child_box)
        meta_row.append(self.author_btn)

        # Rating item
        score_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        score_icon = Gtk.Image.new_from_icon_name("starred-symbolic")
        score_icon.add_css_class("dim-label")
        score_box.append(score_icon)
        self.score_label = Gtk.Label()
        self.score_label.add_css_class("caption")
        self.score_label.add_css_class("dim-label")
        score_box.append(self.score_label)
        meta_row.append(score_box)

        # Downloads item
        dl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        dl_icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
        dl_icon.add_css_class("dim-label")
        dl_box.append(dl_icon)
        self.dl_label = Gtk.Label()
        self.dl_label.add_css_class("caption")
        self.dl_label.add_css_class("dim-label")
        dl_box.append(self.dl_label)
        meta_row.append(dl_box)

        # Version item
        ver_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        ver_icon = Gtk.Image.new_from_icon_name("package-x-generic-symbolic")
        ver_icon.add_css_class("dim-label")
        ver_box.append(ver_icon)
        self.version_label = Gtk.Label()
        self.version_label.add_css_class("caption")
        self.version_label.add_css_class("dim-label")
        ver_box.append(self.version_label)
        meta_row.append(ver_box)

        # Updated item
        updated_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        updated_icon = Gtk.Image.new_from_icon_name("view-refresh-symbolic")
        updated_icon.add_css_class("dim-label")
        updated_box.append(updated_icon)
        self.updated_label = Gtk.Label()
        self.updated_label.add_css_class("caption")
        self.updated_label.add_css_class("dim-label")
        updated_box.append(self.updated_label)
        meta_row.append(updated_box)

        # Added item
        added_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        added_icon = Gtk.Image.new_from_icon_name("x-office-calendar-symbolic")
        added_icon.add_css_class("dim-label")
        added_box.append(added_icon)
        self.added_label = Gtk.Label()
        self.added_label.add_css_class("caption")
        self.added_label.add_css_class("dim-label")
        added_box.append(self.added_label)
        meta_row.append(added_box)

        meta_scroll = Gtk.ScrolledWindow()
        meta_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        meta_scroll.set_child(meta_row)
        content.append(meta_scroll)

        # 4. Package Selector ComboRow inside Adw.PreferencesGroup
        pref_group = Adw.PreferencesGroup()
        pref_group.set_title("Package Selector")

        combo_factory = Gtk.SignalListItemFactory()
        def _setup_combo_item(fact, list_item):
            lbl = Gtk.Label()
            lbl.set_ellipsize(Pango.EllipsizeMode.NONE)
            lbl.set_wrap(True)
            lbl.set_xalign(0)
            lbl.set_margin_start(8)
            lbl.set_margin_end(8)
            lbl.set_margin_top(6)
            lbl.set_margin_bottom(6)
            list_item.set_child(lbl)

        def _bind_combo_item(fact, list_item):
            item = list_item.get_item()
            lbl = list_item.get_child()
            if item and hasattr(item, "get_string"):
                lbl.set_label(item.get_string())

        combo_factory.connect("setup", _setup_combo_item)
        combo_factory.connect("bind", _bind_combo_item)

        self.file_combo_row = Adw.ComboRow()
        self.file_combo_row.set_title("Package File")
        self.file_combo_row.set_subtitle("Select theme package variant to install")
        self.file_combo_row.set_factory(combo_factory)
        self.file_combo_row.set_list_factory(combo_factory)
        self.file_combo_row.connect("notify::selected", self._on_combo_file_selected)
        pref_group.add(self.file_combo_row)
        content.append(pref_group)

        # 5. Adw.ViewSwitcher + Adw.ViewStack for Tabs
        self.view_stack = Adw.ViewStack()

        # Page 1: Description (Plain Gtk.Label, no border/frame/box styling)
        self.desc_label = Gtk.Label()
        self.desc_label.set_wrap(True)
        self.desc_label.set_xalign(0)
        self.desc_label.set_selectable(True)
        self.desc_label.set_margin_top(8)

        desc_page = self.view_stack.add_titled(self.desc_label, "description", "Description")
        desc_page.set_icon_name("document-properties-symbolic")

        # Page 2: Download Files
        self.files_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.files_box.set_margin_top(8)

        files_page = self.view_stack.add_titled(self.files_box, "files", "Download Files")
        files_page.set_icon_name("folder-download-symbolic")

        # Page 3: Changelog
        self.changelog_label = Gtk.Label()
        self.changelog_label.set_wrap(True)
        self.changelog_label.set_xalign(0)
        self.changelog_label.set_selectable(True)
        self.changelog_label.set_margin_top(8)

        changelog_page = self.view_stack.add_titled(self.changelog_label, "changelog", "Changelog")
        changelog_page.set_icon_name("format-justified-symbolic")

        # Page 4: More by Author
        self.more_author_flowbox = Gtk.FlowBox()
        self.more_author_flowbox.set_valign(Gtk.Align.START)
        self.more_author_flowbox.set_halign(Gtk.Align.FILL)
        self.more_author_flowbox.set_max_children_per_line(4)
        self.more_author_flowbox.set_min_children_per_line(1)
        self.more_author_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.more_author_flowbox.set_homogeneous(True)
        self.more_author_flowbox.set_row_spacing(12)
        self.more_author_flowbox.set_column_spacing(12)
        self.more_author_flowbox.set_margin_top(8)
        self.more_author_flowbox.connect("child-activated", self._on_author_card_activated)

        more_page = self.view_stack.add_titled(self.more_author_flowbox, "more_author", "More by Author")
        more_page.set_icon_name("avatar-default-symbolic")

        self.view_switcher = Adw.ViewSwitcher()
        self.view_switcher.set_stack(self.view_stack)
        self.view_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        self.view_switcher.set_halign(Gtk.Align.START)

        content.append(self.view_switcher)
        content.append(self.view_stack)

        scrolled.set_child(content)
        clamp.set_child(scrolled)
        self.toolbar_view.set_content(clamp)

        self.append(self.toolbar_view)

    def set_item(self, item: ThemeItem):
        self.item = item
        if self.favorites_mgr:
            self.item.is_favorite = self.favorites_mgr.is_favorite(item.id)
        self._update_fav_top_button()

        self.title_heading.set_label(item.name)
        self.name_label.set_label(sanitize_text(item.name))

        # Metadata Row
        self.author_avatar.set_text(item.author)
        self.author_avatar.set_custom_image(None)
        self.author_label.set_label(item.author)
        self._load_author_avatar_async(item.author)
        self.score_label.set_label(f"Rating: {item.score}")

        self.version_label.set_label(format_version(item.version))

        updated_str = format_relative_time(item.changed or item.created)
        self.updated_label.set_label(f"updated {updated_str}")

        added_str = format_relative_time(item.created)
        self.added_label.set_label(f"added {added_str}")

        if item.downloads24h:
            self.dl_label.set_label(f"downloads 24h {item.downloads24h}")
        else:
            dl_str = f"{item.downloads:,}" if hasattr(item.downloads, "__format__") else str(item.downloads)
            self.dl_label.set_label(f"downloads {dl_str}")

        has_any_link = False

        if item.source_url:
            self.source_btn.set_uri(item.source_url)
            lbl = f"GitHub: {item.source_url}" if "github.com" in item.source_url.lower() else f"Source Code: {item.source_url}"
            self.source_btn.set_label(lbl)
            self.source_btn.set_tooltip_text(item.source_url)
            self.source_btn.set_visible(True)
            has_any_link = True
        else:
            self.source_btn.set_visible(False)

        if item.detail_page:
            self.store_link_btn.set_uri(item.detail_page)
            self.store_link_btn.set_label(f"Store Page: {item.detail_page}")
            self.store_link_btn.set_tooltip_text(item.detail_page)
            self.store_link_btn.set_visible(True)
            has_any_link = True
        else:
            self.store_link_btn.set_visible(False)

        if item.homepage:
            self.homepage_btn.set_uri(item.homepage)
            self.homepage_btn.set_label(f"Homepage: {item.homepage}")
            self.homepage_btn.set_tooltip_text(item.homepage)
            self.homepage_btn.set_visible(True)
            has_any_link = True
        else:
            self.homepage_btn.set_visible(False)

        self.links_scroll.set_visible(has_any_link)

        # Description Tab (Cleaned Gtk.Label, no border/input frame)
        raw_desc = item.description or item.summary or "No description provided."
        cleaned_desc = sanitize_text(raw_desc)
        self.desc_label.set_label(cleaned_desc)

        # Changelog Tab
        raw_changelog = item.changelog or "No changelog provided for this release."
        cleaned_changelog = sanitize_text(raw_changelog)
        self.changelog_label.set_label(cleaned_changelog)

        # Populate Download Files ComboRow & Tab List
        self._populate_files_list(item.download_files)

        if not item.download_files:
            self._fetch_full_detail_async(item.id)

        # Load Screenshots into Adw.Carousel
        self.preview_textures.clear()
        self._clear_carousel()
        if item.preview_urls:
            self._load_previews_async(item.preview_urls)

        # Fetch More by Author async
        self._fetch_more_by_author_async(item.author)

    def _load_author_avatar_async(self, username: str):
        if not username or username == "Unknown":
            return

        def worker():
            try:
                avatar_url = f"https://www.opendesktop.org/avatar/{username}"
                if avatar_url in IMAGE_CACHE:
                    data = IMAGE_CACHE[avatar_url]
                else:
                    resp = httpx.get(avatar_url, follow_redirects=True, timeout=8.0)
                    if resp.status_code == 200 and resp.content and len(resp.content) > 100:
                        data = resp.content
                        IMAGE_CACHE[avatar_url] = data
                    else:
                        data = None
                if data:
                    GLib.idle_add(self._apply_author_avatar_texture, data, username)
            except Exception as e:
                logger.debug(f"Failed fetching avatar for {username}: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _apply_author_avatar_texture(self, data: bytes, username: str):
        if self.item and self.item.author == username:
            try:
                glib_bytes = GLib.Bytes.new(data)
                texture = Gdk.Texture.new_from_bytes(glib_bytes)
                self.author_avatar.set_custom_image(texture)
            except Exception as e:
                logger.debug(f"Failed applying custom avatar texture for {username}: {e}")

    def _clear_carousel(self):
        child = self.carousel.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.carousel.remove(child)
            child = next_child

    def _update_fav_top_button(self):
        is_fav = self.item.is_favorite if self.item else False
        if is_fav:
            self.fav_top_btn.set_icon_name("starred-symbolic")
            self.fav_top_btn.set_opacity(1.0)
            self.fav_top_btn.add_css_class("accent")
            self.fav_top_btn.remove_css_class("dim-label")
        else:
            self.fav_top_btn.set_icon_name("non-starred-symbolic")
            self.fav_top_btn.set_opacity(0.4)
            self.fav_top_btn.remove_css_class("accent")
            self.fav_top_btn.add_css_class("dim-label")

    def _on_fav_top_clicked(self, btn):
        if self.item and self.favorites_mgr:
            self.item.is_favorite = self.favorites_mgr.toggle_favorite(self.item)
            self._update_fav_top_button()

    def _on_card_fav_toggled(self, item: ThemeItem):
        if self.favorites_mgr:
            self.favorites_mgr.toggle_favorite(item)
            if self.item and self.item.id == item.id:
                self.item.is_favorite = item.is_favorite
                self._update_fav_top_button()

    def _on_author_btn_clicked(self, btn):
        if self.item and self.item.author and self.on_author_clicked:
            self.on_author_clicked(self.item.author)

    def _on_combo_file_selected(self, combo, param):
        idx = combo.get_selected()
        if self.item and self.item.download_files and 0 <= idx < len(self.item.download_files):
            target_file = self.item.download_files[idx]
            name_str = f"{target_file.name} ({target_file.size})" if target_file.size else target_file.name
            combo.set_subtitle(name_str)
            combo.set_tooltip_text(name_str)

    def _populate_files_list(self, files: List[DownloadFile]):
        # Clear files tab container
        child = self.files_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.files_box.remove(child)
            child = next_child

        if files:
            file_names = [f"{f.name} ({f.size})" if f.size else f.name for f in files]
            model = Gtk.StringList.new(file_names)
            self.file_combo_row.set_model(model)
            self.file_combo_row.set_selected(0)
            self.file_combo_row.set_subtitle(file_names[0])
            self.file_combo_row.set_tooltip_text(file_names[0])
            self.install_btn.set_sensitive(True)

            for f in files:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                row.add_css_class("card")
                row.set_margin_top(4)
                row.set_margin_bottom(4)

                icon = Gtk.Image.new_from_icon_name("package-x-generic-symbolic")
                icon.set_pixel_size(24)
                icon.set_margin_start(12)
                row.append(icon)

                lbl_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                lbl_box.set_hexpand(True)
                lbl_box.set_margin_top(8)
                lbl_box.set_margin_bottom(8)

                f_name = Gtk.Label(label=sanitize_text(f.name))
                f_name.add_css_class("heading")
                f_name.set_halign(Gtk.Align.START)
                lbl_box.append(f_name)

                f_meta = Gtk.Label(label=f"Size: {f.size if f.size else 'Unknown'}")
                f_meta.add_css_class("caption")
                f_meta.add_css_class("dim-label")
                f_meta.set_halign(Gtk.Align.START)
                lbl_box.append(f_meta)

                row.append(lbl_box)

                dl_btn = Gtk.Button(label="Download")
                dl_btn.add_css_class("pill")
                dl_btn.add_css_class("flat")
                dl_btn.set_valign(Gtk.Align.CENTER)
                dl_btn.set_margin_end(12)
                url = f.url
                dl_btn.connect("clicked", lambda b, u=url: Gio.AppInfo.launch_default_for_uri(u, None))
                row.append(dl_btn)

                self.files_box.append(row)
        else:
            empty_lbl = Gtk.Label(label="No direct download files listed for this item.")
            empty_lbl.add_css_class("dim-label")
            self.files_box.append(empty_lbl)

    def _fetch_more_by_author_async(self, author: str):
        child = self.more_author_flowbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.more_author_flowbox.remove(child)
            child = next_child

        def worker():
            try:
                author_items, _ = self.ocs_client.search_content(
                    category_type="all",
                    search_query=author,
                    page_size=8
                )
                filtered = [i for i in author_items if i.id != self.item.id][:6]
                GLib.idle_add(self._on_more_by_author_fetched, filtered)
            except Exception as e:
                logger.debug(f"Error fetching more items by author {author}: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_more_by_author_fetched(self, items: List[ThemeItem]):
        fav_ids = self.favorites_mgr.get_favorite_ids() if self.favorites_mgr else set()
        for item in items:
            item.is_favorite = item.id in fav_ids
            card = ThemeCard(item, on_favorite_toggled=self._on_card_fav_toggled)
            self.more_author_flowbox.append(card)

    def _on_author_card_activated(self, flowbox, child_card):
        if isinstance(child_card, ThemeCard):
            self.set_item(child_card.item)

    def _on_open_store_page(self, btn):
        if self.item and self.item.detail_page:
            try:
                Gio.AppInfo.launch_default_for_uri(self.item.detail_page, None)
            except Exception as e:
                logger.error(f"Failed opening store page URL {self.item.detail_page}: {e}")

    def _on_open_homepage(self, btn):
        if self.item and self.item.homepage:
            try:
                Gio.AppInfo.launch_default_for_uri(self.item.homepage, None)
            except Exception as e:
                logger.error(f"Failed opening homepage URL {self.item.homepage}: {e}")

    def _on_open_source_code(self, btn):
        if self.item and self.item.source_url:
            try:
                Gio.AppInfo.launch_default_for_uri(self.item.source_url, None)
            except Exception as e:
                logger.error(f"Failed opening source URL {self.item.source_url}: {e}")

    def _fetch_full_detail_async(self, item_id: str):
        def worker():
            try:
                full_item = self.ocs_client.get_content_detail(item_id)
                GLib.idle_add(self._on_detail_fetched, full_item)
            except Exception as e:
                logger.error(f"Failed fetching item detail: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_detail_fetched(self, full_item: ThemeItem):
        self.item = full_item
        self._populate_files_list(full_item.download_files)
        if full_item.preview_urls and not self.preview_textures:
            self._load_previews_async(full_item.preview_urls)

    def _load_previews_async(self, urls: list[str]):
        self.gallery_spinner.start()
        self.gallery_spinner.set_visible(True)

        def fetch_thread():
            for url in urls:
                try:
                    if url in IMAGE_CACHE:
                        data = IMAGE_CACHE[url]
                    else:
                        resp = httpx.get(url, follow_redirects=True, timeout=10.0)
                        if resp.status_code == 200:
                            data = resp.content
                            IMAGE_CACHE[url] = data
                        else:
                            continue
                    GLib.idle_add(self._add_carousel_picture, data)
                except Exception as e:
                    logger.debug(f"Failed loading detail image {url}: {e}")
            GLib.idle_add(self._on_previews_finished)

        threading.Thread(target=fetch_thread, daemon=True).start()

    def _on_previews_finished(self):
        self.gallery_spinner.stop()
        self.gallery_spinner.set_visible(False)
        has_previews = len(self.preview_textures) > 0
        has_multiple = len(self.preview_textures) > 1
        self.dots.set_visible(has_multiple)
        self.nav_fullscreen.set_visible(has_previews)

    def _on_carousel_h_scroll(self, controller, dx, dy):
        if abs(dx) > 0:
            self._nav_carousel(1 if dx > 0 else -1)
            return True
        return False

    def _nav_carousel(self, delta: int):
        n = self.carousel.get_n_pages()
        if n <= 1:
            return
        pos = round(self.carousel.get_position())
        target = (pos + delta) % n
        page = self.carousel.get_nth_page(target)
        if page:
            self.carousel.scroll_to(page, True)

    def _add_carousel_picture(self, data: bytes):
        try:
            glib_bytes = GLib.Bytes.new(data)
            texture = Gdk.Texture.new_from_bytes(glib_bytes)
            self.preview_textures.append(texture)

            picture = Gtk.Picture()
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            picture.set_size_request(-1, 380)
            picture.set_paintable(texture)
            picture.set_cursor_from_name("zoom-in")

            picture_click = Gtk.GestureClick()
            picture_click.connect("pressed", lambda g, n, x, y, tex=texture: self._open_fullscreen_preview(tex))
            picture.add_controller(picture_click)

            self.carousel.append(picture)
        except Exception as e:
            logger.debug(f"Texture creation error: {e}")

    def _open_fullscreen_preview(self, active_texture: Optional[Gdk.Texture] = None):
        if not self.preview_textures:
            return

        active_idx = 0
        if active_texture and active_texture in self.preview_textures:
            active_idx = self.preview_textures.index(active_texture)

        root_win = self.get_native()
        fullscreen_win = Gtk.Window()
        if root_win:
            fullscreen_win.set_transient_for(root_win)
        fullscreen_win.set_modal(True)
        fullscreen_win.set_title(f"Preview: {self.item.name if self.item else 'Theme'}")
        fullscreen_win.set_default_size(1200, 800)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.add_css_class("dark")

        header = Adw.HeaderBar() if hasattr(Adw, "HeaderBar") else Gtk.HeaderBar()
        header_title = Gtk.Label(label=f"Preview {active_idx + 1} of {len(self.preview_textures)}")
        if hasattr(header, "set_title_widget"):
            header.set_title_widget(header_title)

        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic")
        close_btn.connect("clicked", lambda b: fullscreen_win.close())
        if hasattr(header, "pack_end"):
            header.pack_end(close_btn)

        main_box.append(header)

        img_overlay = Gtk.Overlay()
        img_overlay.set_vexpand(True)
        img_overlay.set_hexpand(True)

        fs_picture = Gtk.Picture()
        fs_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        fs_picture.set_paintable(self.preview_textures[active_idx])
        fs_picture.set_vexpand(True)
        fs_picture.set_hexpand(True)

        fs_click = Gtk.GestureClick()
        fs_click.connect("pressed", lambda g, n, x, y: fullscreen_win.close())
        fs_picture.add_controller(fs_click)

        img_overlay.set_child(fs_picture)
        main_box.append(img_overlay)

        if hasattr(fullscreen_win, "set_content"):
            fullscreen_win.set_content(main_box)
        else:
            fullscreen_win.set_child(main_box)

        fullscreen_win.present()
        fullscreen_win.fullscreen()

    def _on_install_clicked(self, btn):
        if not self.item or not self.item.download_files:
            return

        selected_idx = self.file_combo_row.get_selected()
        if selected_idx < 0 or selected_idx >= len(self.item.download_files):
            return

        target_file = self.item.download_files[selected_idx]

        self.install_btn.set_sensitive(False)
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_visible(True)
        self.progress_label.set_label("Starting download...")
        self.progress_label.set_visible(True)

        def progress_cb(msg: str, pct: float):
            GLib.idle_add(self._update_progress, msg, pct)

        def install_worker():
            try:
                path = self.installer.install_theme_from_url(
                    url=target_file.url,
                    theme_name=self.item.name,
                    type_key=self.item.type_key,
                    progress_cb=progress_cb
                )
                GLib.idle_add(self._on_install_finished, True, path, None)
            except Exception as e:
                logger.error(f"Installation failed: {e}")
                GLib.idle_add(self._on_install_finished, False, "", str(e))

        threading.Thread(target=install_worker, daemon=True).start()

    def _update_progress(self, msg: str, pct: float):
        self.progress_label.set_label(msg)
        self.progress_bar.set_fraction(pct)

    def _on_install_finished(self, success: bool, installed_path: str, error_msg: str):
        self.install_btn.set_sensitive(True)
        self.progress_bar.set_visible(False)

        if success:
            self.installed_path = installed_path
            msg = f"Successfully installed '{self.item.name}'!"
            self.progress_label.set_label(msg)
            if self.gsettings_mgr:
                self.apply_btn.set_visible(True)
            if self.on_installed_toast:
                self.on_installed_toast(msg)
        else:
            self.progress_label.set_label(f"Error: {error_msg}")

    def _on_apply_clicked(self, btn):
        if not self.item or not self.gsettings_mgr:
            return

        theme_name = self.item.name
        if hasattr(self, "installed_path") and self.installed_path:
            theme_name = os.path.basename(self.installed_path)

        success = self.gsettings_mgr.set_theme(self.item.type_key, theme_name)
        if success:
            msg = f"Applied '{theme_name}'!"
            if self.on_installed_toast:
                self.on_installed_toast(msg)
        else:
            msg = f"Failed to apply '{theme_name}'."
            if self.on_installed_toast:
                self.on_installed_toast(msg)

    def _on_back(self):
        self.apply_btn.set_visible(False)
        if self.on_back_clicked:
            self.on_back_clicked()
