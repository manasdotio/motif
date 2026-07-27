"""
Application main window implementation for Motif GTK Theme Manager.
"""
import logging
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Adw, Gdk, Gio, GLib, GObject

from motif.api.ocs_client import OCSClient
from motif.core.installer import ThemeInstaller
from motif.core.theme_scanner import ThemeScanner
from motif.core.gsettings_manager import GSettingsManager
from motif.core.favorites_manager import FavoritesManager
from motif.ui.store_view import StoreView
from motif.ui.detail_view import DetailView
from motif.ui.author_view import AuthorView
from motif.ui.installed_view import InstalledView
from motif.ui.import_dialog import ImportDialog

logger = logging.getLogger(__name__)

class MotifWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title("Motif")
        self.set_default_size(1050, 720)
        self.set_size_request(640, 480)

        # Initialize core components
        self.ocs_client = OCSClient()
        self.installer = ThemeInstaller()
        self.scanner = ThemeScanner()
        self.gsettings_mgr = GSettingsManager()
        self.favorites_mgr = FavoritesManager()

        # Toast Overlay for non-blocking notifications
        self.toast_overlay = Adw.ToastOverlay()

        # Main Box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header Bar
        self.header_bar = Adw.HeaderBar()
        
        # View Switcher Title (Store vs Installed)
        self.view_switcher_title = Adw.ViewSwitcherTitle()
        self.header_bar.set_title_widget(self.view_switcher_title)

        # Import Theme Header Button
        import_hdr_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
        import_hdr_btn.set_tooltip_text("Import Theme from GitHub or URL...")
        import_hdr_btn.connect("clicked", lambda b: self._show_import_dialog())
        self.header_bar.pack_start(import_hdr_btn)

        # GitHub Repository Header Button
        github_hdr_btn = Gtk.Button(label="GitHub")
        github_hdr_btn.add_css_class("flat")
        github_hdr_btn.add_css_class("pill")
        github_hdr_btn.set_tooltip_text("Open GitHub Repository (https://github.com/manas/motif)")
        github_hdr_btn.connect("clicked", lambda b: Gio.AppInfo.launch_default_for_uri("https://github.com/manas/motif", None))
        self.header_bar.pack_end(github_hdr_btn)

        # Menu Button (Primary Menu)
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        
        menu = Gio.Menu()
        menu.append("Import Theme from GitHub / URL...", "win.import_theme")
        menu.append("GitHub Repository", "win.open_github")
        menu.append("Revert Last Change", "win.revert_last")
        menu.append("Refresh Store", "win.refresh_store")
        menu.append("About Motif", "win.about")
        menu_btn.set_menu_model(menu)

        self.header_bar.pack_end(menu_btn)
        main_box.append(self.header_bar)

        # Main View Stack (Store / Installed)
        self.stack = Adw.ViewStack()
        self.view_switcher_title.set_stack(self.stack)

        # 1. Store Page Stack (Store View + Detail View + Author View Sub-Stack)
        self.store_sub_stack = Gtk.Stack()
        self.store_sub_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        # Store View
        self.store_view = StoreView(
            ocs_client=self.ocs_client,
            favorites_mgr=self.favorites_mgr,
            scanner=self.scanner,
            on_item_selected=self._on_store_item_selected,
            on_author_selected=self._on_author_selected
        )
        self.store_sub_stack.add_named(self.store_view, "store_grid")

        # Detail View
        self.detail_view = DetailView(
            ocs_client=self.ocs_client,
            installer=self.installer,
            favorites_mgr=self.favorites_mgr,
            gsettings_mgr=self.gsettings_mgr,
            on_back_clicked=self._on_detail_back,
            on_author_clicked=self._on_author_selected,
            on_installed_toast=self.show_toast
        )
        self.store_sub_stack.add_named(self.detail_view, "store_detail")

        # Author View
        self.author_view = AuthorView(
            ocs_client=self.ocs_client,
            favorites_mgr=self.favorites_mgr,
            on_back_clicked=self._on_author_back,
            on_item_selected=self._on_store_item_selected
        )
        self.store_sub_stack.add_named(self.author_view, "author_view")

        # Add Store page to main ViewStack
        store_page = self.stack.add_titled(self.store_sub_stack, "store", "Store")
        store_page.set_icon_name("system-software-install-symbolic")

        # 2. Installed Page
        self.installed_view = InstalledView(
            scanner=self.scanner,
            gsettings_mgr=self.gsettings_mgr,
            on_toast=self.show_toast,
            on_import_requested=self._show_import_dialog
        )
        installed_page = self.stack.add_titled(self.installed_view, "installed", "Installed")
        installed_page.set_icon_name("emblem-ok-symbolic")

        # Connect view stack page change to refresh installed list if user switches tab
        self.stack.connect("notify::visible-child-name", self._on_tab_changed)

        main_box.append(self.stack)

        # Bottom View Switcher Bar for narrow windows
        switcher_bar = Adw.ViewSwitcherBar()
        switcher_bar.set_stack(self.stack)
        self.view_switcher_title.bind_property(
            "title-visible",
            switcher_bar,
            "reveal",
            GObject.BindingFlags.SYNC_CREATE
        )
        main_box.append(switcher_bar)

        self.toast_overlay.set_child(main_box)
        self.set_content(self.toast_overlay)

        # Mouse Back / Forward side button controller
        mouse_ctrl = Gtk.GestureClick()
        mouse_ctrl.set_button(0)  # Listen to all mouse buttons (including 8 & 9)
        mouse_ctrl.connect("pressed", self._on_window_mouse_pressed)
        self.add_controller(mouse_ctrl)

        # Keyboard Back navigation shortcuts controller (Alt+Left, Esc, Back)
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_window_key_pressed)
        self.add_controller(key_ctrl)

        # Add Window Actions
        self._setup_actions()

    def _on_window_mouse_pressed(self, gesture, n_press, x, y):
        button = gesture.get_current_button()
        # Mouse button 8 is Mouse Back extra button, button 9 is Forward
        if button == 8:
            if self.store_sub_stack.get_visible_child_name() == "store_detail":
                self._on_detail_back()
                return True
        elif button == 9:
            if hasattr(self.detail_view, "item") and self.detail_view.item and self.store_sub_stack.get_visible_child_name() == "store_grid":
                self.store_sub_stack.set_visible_child_name("store_detail")
                return True
        return False

    def _on_window_key_pressed(self, controller, keyval, keycode, state):
        if self.store_sub_stack.get_visible_child_name() == "store_detail":
            if keyval in (Gdk.KEY_Back, Gdk.KEY_Pointer_Left, Gdk.KEY_Escape) or (state & Gdk.ModifierType.ALT_MASK and keyval == Gdk.KEY_Left):
                self._on_detail_back()
                return True
        return False

    def show_toast(self, message: str):
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)

    def _show_import_dialog(self):
        dialog = ImportDialog(
            transient_for=self,
            on_installed_callback=self.installed_view.refresh_installed,
            on_toast_callback=self.show_toast
        )
        dialog.present()

    def _on_store_item_selected(self, item):
        self.header_bar.set_visible(False)
        self.detail_view.set_item(item)
        self.store_sub_stack.set_visible_child_name("store_detail")

    def _on_detail_back(self):
        self.header_bar.set_visible(True)
        self.store_sub_stack.set_visible_child_name("store_grid")

    def _on_author_selected(self, author_name: str):
        self.header_bar.set_visible(False)
        self.author_view.set_author(author_name)
        self.store_sub_stack.set_visible_child_name("author_view")

    def _on_author_back(self):
        self.header_bar.set_visible(True)
        self.store_sub_stack.set_visible_child_name("store_grid")

    def _on_tab_changed(self, stack, param):
        if stack.get_visible_child_name() == "installed":
            self.header_bar.set_visible(True)
            self.installed_view.refresh_installed()
        elif stack.get_visible_child_name() == "store":
            if self.store_sub_stack.get_visible_child_name() == "store_grid":
                self.header_bar.set_visible(True)

    def _setup_actions(self):
        # Action: Import Theme
        action_import = Gio.SimpleAction.new("import_theme", None)
        action_import.connect("activate", lambda a, p: self._show_import_dialog())
        self.add_action(action_import)

        # Action: Open GitHub Repository
        action_github = Gio.SimpleAction.new("open_github", None)
        action_github.connect("activate", lambda a, p: Gio.AppInfo.launch_default_for_uri("https://github.com/manas/motif", None))
        self.add_action(action_github)

        # Action: Revert Last Change
        action_revert = Gio.SimpleAction.new("revert_last", None)
        action_revert.connect("activate", lambda a, p: self._on_revert_action())
        self.add_action(action_revert)

        # Action: Refresh Store
        action_refresh = Gio.SimpleAction.new("refresh_store", None)
        action_refresh.connect("activate", lambda a, p: self.store_view.refresh_store())
        self.add_action(action_refresh)

        # Action: About
        action_about = Gio.SimpleAction.new("about", None)
        action_about.connect("activate", lambda a, p: self._on_about_action())
        self.add_action(action_about)

    def _on_revert_action(self):
        success, msg = self.gsettings_mgr.revert_last_change()
        self.show_toast(msg)
        if success and self.stack.get_visible_child_name() == "installed":
            self.installed_view.refresh_installed()

    def _on_about_action(self):
        about = Adw.AboutDialog.new() if hasattr(Adw, "AboutDialog") else None
        if about:
            about.set_application_name("Motif")
            about.set_version("1.0.0")
            about.set_developer_name("GNOME Desktop Tools")
            about.set_comments("Native GTK4 + Libadwaita theme manager for GNOME desktop.")
            about.set_website("https://github.com/manas/motif")
            about.set_issue_url("https://github.com/manas/motif/issues")
            about.set_license_type(Gtk.License.GPL_3_0)
            about.set_copyright("© 2026 Motif Developers")
            about.present(self)
        else:
            # Fallback for older libadwaita
            win = Adw.AboutWindow.new()
            win.set_transient_for(self)
            win.set_application_name("Motif")
            win.set_version("1.0.0")
            win.set_developer_name("GNOME Desktop Tools")
            win.set_comments("Native GTK4 + Libadwaita theme manager for GNOME desktop.")
            win.set_website("https://github.com/manas/motif")
            win.present()
