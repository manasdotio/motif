"""
Installed view: manages installed themes, radio selector for active theme, deletion,
and inline extension/XCURSOR warnings.
"""
import os
import shutil
import logging
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

from motif.api.models import InstalledTheme
from motif.core.theme_scanner import ThemeScanner
from motif.core.gsettings_manager import GSettingsManager
from motif.core.installer import ThemeInstaller
from motif.core.utils import safe_remove_path

logger = logging.getLogger(__name__)

CATEGORY_TITLES = {
    "gtk": "GTK Themes",
    "shell": "Shell Themes",
    "icon": "Icon Themes",
    "cursor": "Cursor Themes",
    "wallpaper": "Wallpapers"
}

class InstalledView(Adw.PreferencesPage):
    def __init__(self, scanner: ThemeScanner, gsettings_mgr: GSettingsManager, on_toast=None, on_import_requested=None):
        super().__init__()
        self.scanner = scanner
        self.gsettings_mgr = gsettings_mgr
        self.on_toast = on_toast
        self.on_import_requested = on_import_requested
        self._groups = []

        self.refresh_installed()

    def refresh_installed(self):
        # Clear existing groups
        for group in self._groups:
            self.remove(group)
        self._groups.clear()

        # 1. Header / Quick Actions Group
        header_group = Adw.PreferencesGroup()
        header_row = Adw.ActionRow()
        header_row.set_title("Installed Themes")
        header_row.set_subtitle("Manage, switch active state, or delete installed themes")

        self.rollback_btn = Gtk.Button(label="Revert Last Change")
        self.rollback_btn.set_icon_name("edit-undo-symbolic")
        self.rollback_btn.add_css_class("flat")
        self.rollback_btn.set_valign(Gtk.Align.CENTER)
        self.rollback_btn.connect("clicked", self._on_rollback_clicked)
        header_row.add_suffix(self.rollback_btn)

        import_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
        import_btn.add_css_class("flat")
        import_btn.set_tooltip_text("Import Theme from GitHub or URL")
        import_btn.set_valign(Gtk.Align.CENTER)
        import_btn.connect("clicked", self._on_import_clicked)
        header_row.add_suffix(import_btn)

        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.add_css_class("flat")
        refresh_btn.set_tooltip_text("Refresh installed list")
        refresh_btn.set_valign(Gtk.Align.CENTER)
        refresh_btn.connect("clicked", lambda b: self.refresh_installed())
        header_row.add_suffix(refresh_btn)

        header_group.add(header_row)
        self.add(header_group)
        self._groups.append(header_group)

        # 2. Inline Warning Banners
        self._add_warning_banners_if_needed()

        # 3. Get active themes & scan local/system directories
        active_themes = self.gsettings_mgr.get_active_themes()
        installed_items = self.scanner.scan_all(active_themes=active_themes)

        # Group by category type key
        grouped: dict[str, list[InstalledTheme]] = {
            "gtk": [],
            "shell": [],
            "icon": [],
            "cursor": [],
            "wallpaper": []
        }

        for item in installed_items:
            if item.type_key in grouped:
                grouped[item.type_key].append(item)

        # Build UI groups
        for type_key, title in CATEGORY_TITLES.items():
            items = grouped[type_key]
            group = Adw.PreferencesGroup()
            group.set_title(title)
            group.set_description(f"{len(items)} installed")

            if not items:
                row = Adw.ActionRow()
                row.set_title("No items installed in this category")
                group.add(row)
            else:
                # Group radio buttons per category
                first_radio = None
                for theme in items:
                    row = Adw.ActionRow()
                    row.set_title(theme.name)
                    subtitle_parts = [f"Path: {theme.path}"]
                    if theme.variants:
                        subtitle_parts.append(f"Variants: {', '.join(theme.variants)}")
                    row.set_subtitle("  •  ".join(subtitle_parts))

                    # Radio button for active theme selection
                    radio = Gtk.CheckButton()
                    if first_radio is None:
                        first_radio = radio
                    else:
                        radio.set_group(first_radio)

                    if theme.is_active:
                        radio.set_active(True)

                    radio.connect("toggled", self._on_active_toggled, type_key, theme.name)
                    row.add_prefix(radio)
                    row.set_activatable_widget(radio)

                    # Badge for Motif Managed vs System
                    if theme.is_motif_managed:
                        badge = Gtk.Label(label="User")
                        badge.add_css_class("pill")
                        row.add_suffix(badge)

                    # Delete Button (trash icon)
                    delete_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
                    delete_btn.add_css_class("flat")
                    delete_btn.add_css_class("destructive-action")
                    if theme.is_motif_managed:
                        delete_btn.set_tooltip_text("Delete installed theme")
                    else:
                        delete_btn.set_tooltip_text("Delete system theme (requires admin rights)")
                    delete_btn.connect("clicked", self._on_delete_clicked, theme)
                    row.add_suffix(delete_btn)

                    group.add(row)

            self.add(group)
            self._groups.append(group)

    def _add_warning_banners_if_needed(self):
        # 1. Shell Themes extension check
        if not self.gsettings_mgr.is_user_themes_extension_enabled():
            group = Adw.PreferencesGroup()
            banner = Adw.Banner()
            banner.set_title("Shell theme switching requires the 'User Themes' GNOME extension to be enabled.")
            banner.set_button_label("Open Extensions")
            banner.set_revealed(True)
            banner.connect("button-clicked", self._on_open_extensions_clicked)
            group.add(banner)
            self.add(group)
            self._groups.append(group)

        # 2. Wayland XCURSOR_PATH check
        if not self.gsettings_mgr.is_xcursor_path_configured():
            group = Adw.PreferencesGroup()
            banner = Adw.Banner()
            banner.set_title("Wayland Notice: Cursor themes in ~/.local/share/icons may require adding export XCURSOR_PATH to ~/.bashrc")
            banner.set_button_label("Copy Export Command")
            banner.set_revealed(True)
            banner.connect("button-clicked", self._on_copy_xcursor_cmd)
            group.add(banner)
            self.add(group)
            self._groups.append(group)

    def _on_active_toggled(self, radio, type_key: str, theme_name: str):
        if radio.get_active():
            success = self.gsettings_mgr.set_theme(type_key, theme_name)
            if success:
                msg = f"Applied {CATEGORY_TITLES.get(type_key, type_key)}: {theme_name}"
                logger.info(msg)
                if self.on_toast:
                    self.on_toast(msg)
            else:
                msg = f"Failed to apply {CATEGORY_TITLES.get(type_key, type_key)}: {theme_name}"
                logger.error(msg)
                if self.on_toast:
                    self.on_toast(msg)

    def _on_delete_clicked(self, btn, theme: InstalledTheme):
        # Confirm deletion using Adw.AlertDialog (or Adw.MessageDialog fallback)
        root_win = self.get_native()
        
        dialog_title = f"Delete '{theme.name}'?"
        dialog_body = f"Are you sure you want to delete this theme from {theme.path}? This action cannot be undone."

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(dialog_title, dialog_body)
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("delete", "Delete Theme")
            dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")

            def on_response(d, response_id):
                if response_id == "delete":
                    self._perform_delete(theme)

            dialog.connect("response", on_response)
            dialog.present(root_win)
        else:
            # MessageDialog compatibility fallback
            dialog = Adw.MessageDialog.new(root_win, dialog_title, dialog_body)
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("delete", "Delete Theme")
            dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

            def on_response(d, response_id):
                if response_id == "delete":
                    self._perform_delete(theme)

            dialog.connect("response", on_response)
            dialog.present()

    def _perform_delete(self, theme: InstalledTheme):
        try:
            # Requirement: If deleting currently active theme, revert gsettings first!
            if theme.is_active:
                logger.info(f"Reverting active theme '{theme.name}' to default before deletion.")
                self.gsettings_mgr.revert_to_default(theme.type_key)

            # Remove directory/file from disk safely
            safe_remove_path(theme.path)

            msg = f"Deleted '{theme.name}' cleanly."
            logger.info(msg)
            if self.on_toast:
                self.on_toast(msg)

            self.refresh_installed()
        except PermissionError as pe:
            err_msg = f"Permission denied deleting {theme.path}: {pe}"
            logger.error(err_msg)
            if self.on_toast:
                self.on_toast(err_msg)
        except Exception as e:
            err_msg = f"Error deleting {theme.name}: {e}"
            logger.error(err_msg)
            if self.on_toast:
                self.on_toast(err_msg)

    def _on_import_clicked(self, btn):
        if self.on_import_requested:
            self.on_import_requested()

    def _on_rollback_clicked(self, btn):
        success, msg = self.gsettings_mgr.revert_last_change()
        if self.on_toast:
            self.on_toast(msg)
        if success:
            self.refresh_installed()

    def _on_open_extensions_clicked(self, banner):
        try:
            Gio.AppInfo.launch_default_for_uri("gnome-extensions://", None)
        except Exception:
            # Fallback launch gnome-extensions app
            try:
                os.system("gnome-extensions-app &")
            except Exception:
                pass

    def _on_copy_xcursor_cmd(self, banner):
        cmd = 'export XCURSOR_PATH="~/.local/share/icons:~/.icons:$XCURSOR_PATH"'
        clipboard = self.get_display().get_clipboard()
        clipboard.set(cmd)
        if self.on_toast:
            self.on_toast("Copied export command to clipboard!")
