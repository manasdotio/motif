"""
Store view: browse, search, sort, and filter themes with infinite scrolling grid.
Supports scope switching between Themes and Creators/Authors.
"""
import threading
import logging
from typing import Optional, Set, List, Dict
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, GObject

from motif.api.ocs_client import OCSClient, OCSClientError
from motif.api.models import ThemeItem
from motif.core.favorites_manager import FavoritesManager
from motif.core.theme_scanner import ThemeScanner
from motif.ui.widgets.theme_card import ThemeCard
from motif.ui.widgets.author_card import AuthorCard

logger = logging.getLogger(__name__)

CATEGORIES = [
    ("all", "All"),
    ("gtk", "GTK Themes"),
    ("shell", "Shell Themes"),
    ("icon", "Icon Themes"),
    ("cursor", "Cursor Themes"),
    ("wallpaper", "Wallpapers"),
    ("favorites", "⭐ Favorites"),
]

SORT_OPTIONS = [
    ("relevance", "Relevance"),
    ("rating", "Rating"),
    ("downloads", "Downloads"),
    ("newest", "Newest"),
    ("name", "Name"),
]

STYLE_OPTIONS = [
    ("all", "All Styles"),
    ("dark", "Dark Mode"),
    ("light", "Light Mode"),
    ("gtk4", "GTK4 / Libadwaita"),
]

SEARCH_SCOPES = [
    ("themes", "Themes"),
    ("creators", "Creators"),
]

class StoreView(Gtk.Box):
    def __init__(
        self,
        ocs_client: OCSClient,
        favorites_mgr: Optional[FavoritesManager] = None,
        scanner: Optional[ThemeScanner] = None,
        on_item_selected=None,
        on_author_selected=None
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.ocs_client = ocs_client
        self.favorites_mgr = favorites_mgr
        self.scanner = scanner or ThemeScanner()
        self.on_item_selected = on_item_selected
        self.on_author_selected = on_author_selected

        self.current_category = "all"
        self.current_sort = "rating"
        self.current_style = "all"
        self.search_scope = "themes"
        self.hide_installed = False
        self.search_query = ""
        self.current_page = 1
        self.total_items = 0
        self.is_loading = False
        self.has_more = True
        self.search_debounce_id = None
        self.items: list[ThemeItem] = []
        self._installed_names_cache: Set[str] = set()
        self._rendered_author_names: Set[str] = set()
        self._rendered_item_ids: Set[str] = set()

        # Cache installed theme names for fast filtering
        self._update_installed_cache()

        # Header controls bar (Search + Scope + Sort + Style Filter + Hide Installed + Category Pills)
        controls_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        controls_box.set_margin_start(16)
        controls_box.set_margin_end(16)
        controls_box.set_margin_top(12)
        controls_box.set_margin_bottom(12)

        # Top row: Search Bar + Search Scope + Sort Dropdown + Style Dropdown + Hide Installed Toggle
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text("Search themes or creators...")
        self.search_entry.connect("search-changed", self._on_search_changed)
        top_row.append(self.search_entry)

        # Search Scope Switcher (Themes vs Creators)
        scope_names = [label for _, label in SEARCH_SCOPES]
        scope_model = Gtk.StringList.new(scope_names)
        self.scope_dropdown = Gtk.DropDown.new(scope_model, None)
        self.scope_dropdown.set_selected(0)
        self.scope_dropdown.set_tooltip_text("Search scope: Themes or Creators")
        self.scope_dropdown.connect("notify::selected", self._on_scope_changed)
        top_row.append(self.scope_dropdown)

        # Sort Dropdown
        sort_names = [label for _, label in SORT_OPTIONS]
        sort_model = Gtk.StringList.new(sort_names)
        self.sort_dropdown = Gtk.DropDown.new(sort_model, None)
        self.sort_dropdown.set_selected(0)
        self.sort_dropdown.set_tooltip_text("Sort order")
        self.sort_dropdown.connect("notify::selected", self._on_sort_changed)
        top_row.append(self.sort_dropdown)

        # Style / Format Filter Dropdown
        style_names = [label for _, label in STYLE_OPTIONS]
        style_model = Gtk.StringList.new(style_names)
        self.style_dropdown = Gtk.DropDown.new(style_model, None)
        self.style_dropdown.set_selected(0)
        self.style_dropdown.set_tooltip_text("Filter by Style / Variant")
        self.style_dropdown.connect("notify::selected", self._on_style_changed)
        top_row.append(self.style_dropdown)

        # Hide Installed Toggle Button
        self.hide_installed_btn = Gtk.ToggleButton(label="Hide Installed")
        self.hide_installed_btn.add_css_class("pill")
        self.hide_installed_btn.set_tooltip_text("Filter out themes that are already installed on your system")
        self.hide_installed_btn.connect("toggled", self._on_hide_installed_toggled)
        top_row.append(self.hide_installed_btn)

        controls_box.append(top_row)

        # Category Pills Row
        pills_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pills_box.set_halign(Gtk.Align.START)

        self.pill_buttons = {}
        first_btn = None

        for cat_key, cat_label in CATEGORIES:
            btn = Gtk.ToggleButton(label=cat_label)
            btn.add_css_class("pill")
            if first_btn is None:
                first_btn = btn
                btn.set_active(True)
            else:
                btn.set_group(first_btn)

            btn.connect("toggled", self._on_category_toggled, cat_key)
            pills_box.append(btn)
            self.pill_buttons[cat_key] = btn

        pills_scroll = Gtk.ScrolledWindow()
        pills_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        pills_scroll.set_child(pills_box)
        controls_box.append(pills_scroll)

        self.append(controls_box)

        # Main Content Area (Overlay with FlowBox / ScrolledWindow & StatusPage)
        self.overlay = Gtk.Overlay()
        self.overlay.set_vexpand(True)

        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_halign(Gtk.Align.FILL)
        self.flowbox.set_max_children_per_line(5)
        self.flowbox.set_min_children_per_line(1)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_row_spacing(16)
        self.flowbox.set_column_spacing(16)
        self.flowbox.set_margin_start(16)
        self.flowbox.set_margin_end(16)
        self.flowbox.set_margin_top(16)
        self.flowbox.set_margin_bottom(24)
        self.flowbox.connect("child-activated", self._on_card_activated)

        self.scrolled_window.set_child(self.flowbox)
        self.overlay.set_child(self.scrolled_window)

        # Connect infinite scroll
        vadjust = self.scrolled_window.get_vadjustment()
        vadjust.connect("value-changed", self._on_scroll_value_changed)

        # Status Page (Loading, Empty, Error)
        self.status_page = Adw.StatusPage()
        self.status_page.set_visible(False)
        self.overlay.add_overlay(self.status_page)

        # Bottom Infinite Scroll Loader Box
        self.bottom_loading_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.bottom_loading_box.add_css_class("card")
        self.bottom_loading_box.add_css_class("pill")
        self.bottom_loading_box.set_halign(Gtk.Align.CENTER)
        self.bottom_loading_box.set_valign(Gtk.Align.END)
        self.bottom_loading_box.set_margin_bottom(16)

        self.bottom_spinner = Gtk.Spinner()
        self.bottom_spinner.set_size_request(20, 20)
        self.bottom_loading_box.append(self.bottom_spinner)

        loading_label = Gtk.Label(label="Loading more items...")
        loading_label.add_css_class("body")
        loading_label.add_css_class("heading")
        self.bottom_loading_box.append(loading_label)

        self.bottom_loading_box.set_visible(False)
        self.overlay.add_overlay(self.bottom_loading_box)

        self.append(self.overlay)

        # Initial fetch
        self.refresh_store()

    def _update_installed_cache(self):
        try:
            installed = self.scanner.scan_all()
            self._installed_names_cache = {t.name.lower().strip() for t in installed}
        except Exception as e:
            logger.warning(f"Error scanning installed themes for filter: {e}")
            self._installed_names_cache = set()

    def _on_category_toggled(self, btn, cat_key):
        if btn.get_active():
            self.current_category = cat_key
            self.refresh_store()

    def _on_scope_changed(self, dropdown, param):
        idx = dropdown.get_selected()
        if 0 <= idx < len(SEARCH_SCOPES):
            self.search_scope = SEARCH_SCOPES[idx][0]
            self.refresh_store()

    def _on_search_changed(self, entry):
        if self.search_debounce_id:
            GLib.source_remove(self.search_debounce_id)
            self.search_debounce_id = None

        self.search_debounce_id = GLib.timeout_add(300, self._perform_search_debounce)

    def _perform_search_debounce(self):
        self.search_debounce_id = None
        self.search_query = self.search_entry.get_text().strip()
        self.refresh_store()
        return False

    def _on_sort_changed(self, dropdown, param):
        idx = dropdown.get_selected()
        if 0 <= idx < len(SORT_OPTIONS):
            self.current_sort = SORT_OPTIONS[idx][0]
            self.refresh_store()

    def _on_style_changed(self, dropdown, param):
        idx = dropdown.get_selected()
        if 0 <= idx < len(STYLE_OPTIONS):
            self.current_style = STYLE_OPTIONS[idx][0]
            self.refresh_store()

    def _on_hide_installed_toggled(self, btn):
        self.hide_installed = btn.get_active()
        if self.hide_installed:
            self._update_installed_cache()
        self.refresh_store()

    def _on_scroll_value_changed(self, vadjustment):
        val = vadjustment.get_value()
        max_val = vadjustment.get_upper() - vadjustment.get_page_size()
        if max_val > 0 and val >= max_val - 100:
            if not self.is_loading and self.has_more and self.current_category != "favorites":
                self.load_next_page()

    def _item_passes_filters(self, item: ThemeItem) -> bool:
        if self.hide_installed:
            item_name_norm = item.name.lower().strip()
            if item_name_norm in self._installed_names_cache:
                return False
            item_clean = item_name_norm.replace("-", " ").replace("_", " ")
            for inst in self._installed_names_cache:
                inst_clean = inst.replace("-", " ").replace("_", " ")
                if item_clean == inst_clean or item_clean in inst_clean or inst_clean in item_clean:
                    return False

        if self.current_style != "all":
            search_text = (item.name + " " + item.summary + " " + item.description).lower()
            if self.current_style == "dark":
                if "light" in search_text and "dark" not in search_text:
                    return False
            elif self.current_style == "light":
                if "dark" in search_text and "light" not in search_text:
                    return False
            elif self.current_style == "gtk4":
                if "gtk2" in search_text or "gtk 2" in search_text:
                    return False

        return True

    def refresh_store(self):
        self.current_page = 1
        self.has_more = True
        self.items.clear()
        self._rendered_author_names.clear()
        self._rendered_item_ids.clear()

        child = self.flowbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.flowbox.remove(child)
            child = next_child

        if self.current_category == "favorites":
            self._display_favorites()
        else:
            self._show_loading_state()
            self._fetch_page_async(1)

    def _display_favorites(self):
        self.is_loading = False
        self.has_more = False
        self.bottom_loading_box.set_visible(False)

        if not self.favorites_mgr:
            self._show_empty_state()
            return

        fav_items = self.favorites_mgr.get_favorites()
        query = self.search_query.lower()

        filtered_favs = []
        for item in fav_items:
            if query:
                item_text = (item.name + " " + item.author + " " + item.summary + " " + item.description).lower()
                if query not in item_text:
                    continue
            if self._item_passes_filters(item):
                item.is_favorite = True
                filtered_favs.append(item)

        if self.current_sort == "rating":
            filtered_favs.sort(key=lambda x: x.score, reverse=True)
        elif self.current_sort == "downloads":
            filtered_favs.sort(key=lambda x: x.downloads, reverse=True)
        elif self.current_sort == "newest":
            filtered_favs.sort(key=lambda x: x.created, reverse=True)
        elif self.current_sort == "name":
            filtered_favs.sort(key=lambda x: x.name.lower())

        if not filtered_favs:
            self.status_page.set_title("No Favorite Themes")
            self.status_page.set_description("Star themes while browsing to save them in your favorites collection.")
            self.status_page.set_icon_name("starred-symbolic")
            self.status_page.set_child(None)
            self.status_page.set_visible(True)
            return

        self.status_page.set_visible(False)

        for item in filtered_favs:
            card = ThemeCard(item, on_favorite_toggled=self._on_card_fav_toggled)
            self.flowbox.append(card)

    def _on_card_fav_toggled(self, item: ThemeItem):
        if self.favorites_mgr:
            self.favorites_mgr.toggle_favorite(item)
            if self.current_category == "favorites":
                self.refresh_store()

    def load_next_page(self):
        if self.is_loading or not self.has_more or self.current_category == "favorites":
            return
        next_page = self.current_page + 1
        self.is_loading = True
        self.bottom_spinner.start()
        self.bottom_loading_box.set_visible(True)
        self._fetch_page_async(next_page)

    def _show_loading_state(self):
        msg = "Searching Creators..." if self.search_scope == "creators" else "Loading Themes..."
        self.status_page.set_title(msg)
        self.status_page.set_description("Connecting to gnome-look store...")
        self.status_page.set_icon_name("process-working-symbolic")
        self.status_page.set_child(None)
        self.status_page.set_visible(True)

    def _show_error_state(self, error_msg: str):
        self.status_page.set_title("Could Not Load Store")
        self.status_page.set_description(f"Network failure: {error_msg}")
        self.status_page.set_icon_name("network-error-symbolic")

        retry_btn = Gtk.Button(label="Try Again")
        retry_btn.add_css_class("suggested-action")
        retry_btn.add_css_class("pill")
        retry_btn.set_halign(Gtk.Align.CENTER)
        retry_btn.connect("clicked", lambda b: self.refresh_store())
        self.status_page.set_child(retry_btn)
        self.status_page.set_visible(True)

    def _show_empty_state(self):
        if self.search_scope == "creators":
            self.status_page.set_title("No Creators Found")
            self.status_page.set_description("No authors matched your search term.")
            self.status_page.set_icon_name("avatar-default-symbolic")
        else:
            self.status_page.set_title("No Themes Found")
            self.status_page.set_description("Try refining your search terms or selecting another category.")
            self.status_page.set_icon_name("system-search-symbolic")
        self.status_page.set_child(None)
        self.status_page.set_visible(True)

    def _fetch_page_async(self, page_num: int):
        self.is_loading = True

        cat_key = self.current_category
        sort_mode = self.current_sort
        query = self.search_query.strip()
        if self.current_style != "all":
            style_term = "dark" if self.current_style == "dark" else ("light" if self.current_style == "light" else "gtk4")
            query = f"{query} {style_term}".strip()

        def fetch_thread():
            try:
                new_items, total_count = self.ocs_client.search_content(
                    category_type=cat_key,
                    search_query=query,
                    sort_mode=sort_mode,
                    page=page_num,
                    page_size=30
                )
                GLib.idle_add(self._on_page_fetched, page_num, new_items, total_count, None)
            except Exception as e:
                logger.error(f"Error fetching store page {page_num}: {e}")
                GLib.idle_add(self._on_page_fetched, page_num, [], 0, str(e))

        threading.Thread(target=fetch_thread, daemon=True).start()

    def _on_page_fetched(self, page_num: int, new_items: list[ThemeItem], total_count: int, error: str):
        self.is_loading = False
        self.bottom_spinner.stop()
        self.bottom_loading_box.set_visible(False)

        if error:
            if page_num == 1:
                self._show_error_state(error)
            return

        self.current_page = page_num
        self.total_items = total_count

        if self.favorites_mgr:
            fav_ids = self.favorites_mgr.get_favorite_ids()
            for item in new_items:
                item.is_favorite = item.id in fav_ids

        display_items = [item for item in new_items if self._item_passes_filters(item)]

        if self.search_scope == "creators":
            # Group items by author to render AuthorCards
            authors_map: Dict[str, List[ThemeItem]] = {}
            for item in display_items:
                if item.author:
                    if self.search_query and self.search_query.lower() not in item.author.lower():
                        continue
                    authors_map.setdefault(item.author, []).append(item)

            for author_name, author_items in authors_map.items():
                if author_name.lower() in self._rendered_author_names:
                    continue
                self._rendered_author_names.add(author_name.lower())
                titles = [it.name for it in author_items]
                card = AuthorCard(
                    author_name=author_name,
                    theme_count=len(author_items),
                    sample_titles=titles,
                    on_author_clicked=self._on_author_card_clicked
                )
                self.flowbox.append(card)
        else:
            unique_display_items = []
            for item in display_items:
                if item.id not in self._rendered_item_ids:
                    self._rendered_item_ids.add(item.id)
                    unique_display_items.append(item)

            self.items.extend(unique_display_items)

            if len(new_items) < 30 or len(self.items) >= total_count:
                self.has_more = False

            if page_num == 1 and not self.items:
                if self.has_more and new_items:
                    self.load_next_page()
                    return
                self._show_empty_state()
                return

            self.status_page.set_visible(False)

            # Append ThemeCards
            for item in unique_display_items:
                card = ThemeCard(item, on_favorite_toggled=self._on_card_fav_toggled)
                self.flowbox.append(card)

    def _on_author_card_clicked(self, author_name: str):
        if self.on_author_selected:
            self.on_author_selected(author_name)

    def _on_card_activated(self, flowbox, child_card):
        if isinstance(child_card, ThemeCard) and self.on_item_selected:
            self.on_item_selected(child_card.item)
        elif isinstance(child_card, AuthorCard) and self.on_author_selected:
            self.on_author_selected(child_card.author_name)
