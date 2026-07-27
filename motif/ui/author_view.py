"""
Creator profile view displaying creator Adw.Avatar, profile details, statistics, sort control, and theme items grid.
Structured with Adw.ToolbarView, Adw.Clamp, Adw.Avatar, and reused Store sort options.
"""
import threading
import logging
from typing import Optional, List, Dict
import httpx
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Adw, Gdk, GLib, Gio, GObject

from motif.api.ocs_client import OCSClient
from motif.api.models import ThemeItem
from motif.core.favorites_manager import FavoritesManager
from motif.ui.widgets.theme_card import ThemeCard, IMAGE_CACHE
from motif.ui.store_view import SORT_OPTIONS
from motif.ui.detail_view import sanitize_text

logger = logging.getLogger(__name__)

class AuthorView(Gtk.Box):
    def __init__(
        self,
        ocs_client: OCSClient,
        favorites_mgr: Optional[FavoritesManager] = None,
        on_back_clicked=None,
        on_item_selected=None
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.ocs_client = ocs_client
        self.favorites_mgr = favorites_mgr
        self.on_back_clicked = on_back_clicked
        self.on_item_selected = on_item_selected

        self.author_name = ""
        self.current_sort = "rating"
        self.is_loading = False
        self.items: List[ThemeItem] = []
        self.person_detail: Dict = {}

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

        self.title_heading = Gtk.Label(label="Creator Profile")
        self.title_heading.add_css_class("title-2")
        self.title_heading.set_halign(Gtk.Align.START)
        self.header_bar.set_title_widget(self.title_heading)

        self.toolbar_view.add_top_bar(self.header_bar)

        # Main Content inside Adw.Clamp
        clamp = Adw.Clamp()
        clamp.set_maximum_size(1050)
        clamp.set_tightening_threshold(850)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(24)

        # 1. Connected Header Card (Adw.Avatar + Bio Info + Right-aligned Stats)
        header_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        header_card.add_css_class("card")
        header_card.set_margin_top(4)
        header_card.set_margin_bottom(4)

        card_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card_inner.set_margin_start(20)
        card_inner.set_margin_end(20)
        card_inner.set_margin_top(20)
        card_inner.set_margin_bottom(20)
        card_inner.set_hexpand(True)

        # Top identity row: Avatar + Name/Subtitle + Stats
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        top_row.set_valign(Gtk.Align.CENTER)

        # Avatar (size=64, vertically centered with name)
        self.avatar = Adw.Avatar.new(64, "", True)
        self.avatar.set_valign(Gtk.Align.CENTER)
        top_row.append(self.avatar)

        # Name + Subtitle (centered vertically with avatar)
        name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name_box.set_valign(Gtk.Align.CENTER)
        name_box.set_hexpand(True)

        self.author_heading = Gtk.Label(label="Creator")
        self.author_heading.add_css_class("title-1")
        self.author_heading.set_halign(Gtk.Align.START)
        self.author_heading.set_xalign(0)
        name_box.append(self.author_heading)

        self.author_subtitle = Gtk.Label(label="Creator on gnome-look.org")
        self.author_subtitle.add_css_class("caption")
        self.author_subtitle.add_css_class("dim-label")
        self.author_subtitle.set_halign(Gtk.Align.START)
        self.author_subtitle.set_xalign(0)
        name_box.append(self.author_subtitle)

        top_row.append(name_box)

        # Right: Stats vertical box
        stats_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        stats_vbox.set_valign(Gtk.Align.CENTER)
        stats_vbox.set_halign(Gtk.Align.END)

        self.items_count_badge = Gtk.Label(label="0 Themes")
        self.items_count_badge.add_css_class("heading")
        self.items_count_badge.set_halign(Gtk.Align.END)
        stats_vbox.append(self.items_count_badge)

        self.total_dl_badge = Gtk.Label(label="0 Downloads")
        self.total_dl_badge.add_css_class("caption")
        self.total_dl_badge.add_css_class("dim-label")
        self.total_dl_badge.set_halign(Gtk.Align.END)
        stats_vbox.append(self.total_dl_badge)

        top_row.append(stats_vbox)

        card_inner.append(top_row)

        # Bio description & Web Profile Link below top_row
        self.bio_label = Gtk.Label()
        self.bio_label.add_css_class("body")
        self.bio_label.set_halign(Gtk.Align.START)
        self.bio_label.set_wrap(True)
        self.bio_label.set_xalign(0)
        self.bio_label.set_visible(False)
        card_inner.append(self.bio_label)

        self.web_profile_btn = Gtk.Button(label="Visit Profile Web Page")
        self.web_profile_btn.set_icon_name("external-link-symbolic")
        self.web_profile_btn.add_css_class("pill")
        self.web_profile_btn.add_css_class("flat")
        self.web_profile_btn.set_halign(Gtk.Align.START)
        self.web_profile_btn.set_visible(False)
        self.web_profile_btn.connect("clicked", self._on_web_profile_clicked)
        card_inner.append(self.web_profile_btn)

        header_card.append(card_inner)
        main_box.append(header_card)

        # 2. Sort Dropdown Control Row (reused from Store page)
        sort_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        sort_row.set_halign(Gtk.Align.END)

        sort_label = Gtk.Label(label="Sort:")
        sort_label.add_css_class("caption")
        sort_label.add_css_class("dim-label")
        sort_row.append(sort_label)

        sort_names = [label for _, label in SORT_OPTIONS]
        sort_model = Gtk.StringList.new(sort_names)
        self.sort_dropdown = Gtk.DropDown.new(sort_model, None)
        self.sort_dropdown.set_selected(0)
        self.sort_dropdown.connect("notify::selected", self._on_sort_changed)
        sort_row.append(self.sort_dropdown)

        main_box.append(sort_row)

        # 3. Grid Container inside ScrolledWindow (vexpand naturally)
        self.overlay = Gtk.Overlay()
        self.overlay.set_vexpand(True)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_halign(Gtk.Align.FILL)
        self.flowbox.set_max_children_per_line(4)
        self.flowbox.set_min_children_per_line(1)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_row_spacing(16)
        self.flowbox.set_column_spacing(16)
        self.flowbox.connect("child-activated", self._on_card_activated)

        grid_scroll = Gtk.ScrolledWindow()
        grid_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        grid_scroll.set_vexpand(True)
        grid_scroll.set_child(self.flowbox)

        self.overlay.set_child(grid_scroll)

        # Status Page (displayed only on empty/error)
        self.status_page = Adw.StatusPage()
        self.status_page.set_visible(False)
        self.overlay.add_overlay(self.status_page)

        main_box.append(self.overlay)
        clamp.set_child(main_box)
        self.toolbar_view.set_content(clamp)

        self.append(self.toolbar_view)

    def set_author(self, author_name: str):
        """Sets active author and fetches published themes and profile avatar."""
        self.author_name = author_name
        self.author_heading.set_label(f"@{author_name}")
        self.title_heading.set_label(f"Creator: {author_name}")
        self.avatar.set_text(author_name)
        self.items.clear()
        self.person_detail.clear()
        self.bio_label.set_visible(False)
        self.web_profile_btn.set_visible(False)

        # Clear existing flowbox children
        child = self.flowbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.flowbox.remove(child)
            child = next_child

        self._show_loading_state()
        self._fetch_author_items_async()
        self._fetch_author_avatar_async(author_name)

    def _fetch_author_avatar_async(self, author_name: str):
        def worker():
            try:
                person = self.ocs_client.get_person_detail(author_name)
                avatar_url = person.get("bigavatarpic") or person.get("avatarpic") or self.ocs_client.get_avatar_url(author_name)
                web_profile = person.get("profilepage") or person.get("homepage") or ""

                GLib.idle_add(self._update_person_info, person, web_profile)

                if avatar_url in IMAGE_CACHE:
                    data = IMAGE_CACHE[avatar_url]
                    GLib.idle_add(self._set_avatar_texture, data)
                else:
                    with httpx.Client(follow_redirects=True, timeout=8.0) as client:
                        resp = client.get(avatar_url)
                        if resp.status_code == 200:
                            data = resp.content
                            IMAGE_CACHE[avatar_url] = data
                            GLib.idle_add(self._set_avatar_texture, data)
            except Exception as e:
                logger.debug(f"Failed loading avatar for {author_name}: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _update_person_info(self, person: Dict, web_profile: str):
        self.person_detail = person
        fname = person.get("firstname", "").strip()
        lname = person.get("lastname", "").strip()
        full_name = f"{fname} {lname}".strip()

        if full_name:
            self.author_heading.set_label(full_name)
            self.author_subtitle.set_label(f"@{self.author_name} • Creator on gnome-look.org")
            self.avatar.set_text(full_name)
        else:
            self.author_heading.set_label(f"@{self.author_name}")
            self.author_subtitle.set_label("Creator on gnome-look.org")
            self.avatar.set_text(self.author_name)

        bio = person.get("description", "").strip()
        if bio:
            self.bio_label.set_label(sanitize_text(bio))
            self.bio_label.set_visible(True)

        if web_profile:
            self.web_profile_btn.set_visible(True)

    def _set_avatar_texture(self, data: bytes):
        try:
            glib_bytes = GLib.Bytes.new(data)
            texture = Gdk.Texture.new_from_bytes(glib_bytes)
            self.avatar.set_custom_image(texture)
        except Exception as e:
            logger.debug(f"Error rendering avatar texture: {e}")

    def _on_web_profile_clicked(self, btn):
        url = self.person_detail.get("profilepage") or self.person_detail.get("homepage")
        if url:
            try:
                Gio.AppInfo.launch_default_for_uri(url, None)
            except Exception as e:
                logger.error(f"Failed opening profile URL {url}: {e}")

    def _on_sort_changed(self, dropdown, param):
        idx = dropdown.get_selected()
        if 0 <= idx < len(SORT_OPTIONS):
            self.current_sort = SORT_OPTIONS[idx][0]
            self._render_items_grid()

    def _show_loading_state(self):
        self.status_page.set_title(f"Loading themes by @{self.author_name}...")
        self.status_page.set_description("Searching gnome-look store for author creations...")
        self.status_page.set_icon_name("process-working-symbolic")
        self.status_page.set_child(None)
        self.status_page.set_visible(True)

    def _show_empty_state(self):
        self.status_page.set_title(f"No Themes Found for @{self.author_name}")
        self.status_page.set_description("This creator has no public theme packages listed.")
        self.status_page.set_icon_name("avatar-default-symbolic")
        self.status_page.set_child(None)
        self.status_page.set_visible(True)

    def _fetch_author_items_async(self):
        self.is_loading = True
        author = self.author_name

        def fetch_thread():
            try:
                new_items, total_count = self.ocs_client.search_content(
                    category_type="all",
                    search_query=author,
                    page=1,
                    page_size=60
                )
                author_filtered = [
                    item for item in new_items
                    if item.author.lower().strip() == author.lower().strip()
                    or author.lower().strip() in item.author.lower().strip()
                ]
                GLib.idle_add(self._on_items_fetched, author_filtered, None)
            except Exception as e:
                logger.error(f"Error fetching themes for author {author}: {e}")
                GLib.idle_add(self._on_items_fetched, [], str(e))

        threading.Thread(target=fetch_thread, daemon=True).start()

    def _on_items_fetched(self, new_items: List[ThemeItem], error: str):
        self.is_loading = False

        if error:
            self.status_page.set_title("Error Loading Author Profile")
            self.status_page.set_description(error)
            self.status_page.set_icon_name("network-error-symbolic")
            self.status_page.set_visible(True)
            return

        self.items = new_items
        total_dls = sum(item.downloads for item in self.items)

        self.items_count_badge.set_label(f"{len(self.items)} Themes")
        if total_dls > 1000:
            self.total_dl_badge.set_label(f"⬇ {total_dls / 1000:.1f}k Downloads")
        else:
            self.total_dl_badge.set_label(f"⬇ {total_dls} Downloads")

        if not self.items:
            self._show_empty_state()
            return

        self.status_page.set_visible(False)
        self._render_items_grid()

    def _render_items_grid(self):
        # Clear flowbox
        child = self.flowbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.flowbox.remove(child)
            child = next_child

        # Sort items based on current_sort
        if self.current_sort == "relevance":
            sorted_items = sorted(self.items, key=lambda x: x.score, reverse=True)
        elif self.current_sort == "rating":
            sorted_items = sorted(self.items, key=lambda x: x.score, reverse=True)
        elif self.current_sort == "downloads":
            sorted_items = sorted(self.items, key=lambda x: x.downloads, reverse=True)
        elif self.current_sort == "newest":
            sorted_items = sorted(self.items, key=lambda x: x.created, reverse=True)
        elif self.current_sort == "name":
            sorted_items = sorted(self.items, key=lambda x: x.name.lower())
        else:
            sorted_items = self.items

        fav_ids = self.favorites_mgr.get_favorite_ids() if self.favorites_mgr else set()
        for item in sorted_items:
            item.is_favorite = item.id in fav_ids
            card = ThemeCard(item, on_favorite_toggled=self._on_fav_toggled)
            self.flowbox.append(card)

    def _on_fav_toggled(self, item: ThemeItem):
        if self.favorites_mgr:
            self.favorites_mgr.toggle_favorite(item)

    def _on_card_activated(self, flowbox, child_card):
        if isinstance(child_card, ThemeCard) and self.on_item_selected:
            self.on_item_selected(child_card.item)

    def _on_back(self):
        if self.on_back_clicked:
            self.on_back_clicked()
