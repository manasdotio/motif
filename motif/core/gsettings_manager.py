"""
GSettings Manager: direct wrapper around Gio.Settings for GNOME theme application,
User Themes extension detection, XCURSOR_PATH check, GTK4 linking, and rollback history.
"""
import os
import shutil
import subprocess
import logging
from typing import Dict, Optional, Tuple, List, Any
import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio

logger = logging.getLogger(__name__)

# Default GNOME fallbacks
DEFAULT_THEMES = {
    "gtk": "Adwaita",
    "icon": "Adwaita",
    "cursor": "Adwaita",
    "shell": "",
    "wallpaper": ""
}

INTERFACE_SCHEMA = "org.gnome.desktop.interface"
SHELL_SCHEMA = "org.gnome.shell"
USER_THEME_SCHEMA = "org.gnome.shell.extensions.user-theme"
BACKGROUND_SCHEMA = "org.gnome.desktop.background"

USER_THEME_UUID = "user-theme@gnome-shell-extensions.gcampax.github.com"

class GSettingsManager:
    def __init__(self):
        self._history: List[Tuple[str, str, str, str]] = []  # (schema_id, key, old_val, new_val)
        self._settings_cache: Dict[str, Optional[Gio.Settings]] = {}
        self.home_dir = os.path.expanduser("~")

    def _get_settings(self, schema_id: str) -> Optional[Gio.Settings]:
        if schema_id in self._settings_cache:
            return self._settings_cache[schema_id]

        source = Gio.SettingsSchemaSource.get_default()
        if source and source.lookup(schema_id, True):
            settings = Gio.Settings.new(schema_id)
            self._settings_cache[schema_id] = settings
            return settings

        self._settings_cache[schema_id] = None
        return None

    def is_schema_available(self, schema_id: str) -> bool:
        """Checks if a GSettings schema is installed on the system."""
        return self._get_settings(schema_id) is not None

    def is_user_themes_extension_enabled(self) -> bool:
        """
        Checks if GNOME Shell User Themes extension is installed and enabled.
        """
        if not self.is_schema_available(USER_THEME_SCHEMA):
            return False

        shell_settings = self._get_settings(SHELL_SCHEMA)
        if shell_settings:
            try:
                enabled_exts = shell_settings.get_strv("enabled-extensions")
                if USER_THEME_UUID in enabled_exts or any("user-theme" in ext for ext in enabled_exts):
                    return True
            except Exception as e:
                logger.warning(f"Failed to read enabled-extensions: {e}")

        # If user-theme schema exists and accessible, treat as available/enabled
        return True

    @staticmethod
    def is_xcursor_path_configured() -> bool:
        """
        Checks if XCURSOR_PATH environment variable includes local icons directory on Wayland.
        """
        xcursor_path = os.environ.get("XCURSOR_PATH", "")
        home_icons = os.path.expanduser("~/.local/share/icons")
        dot_icons = os.path.expanduser("~/.icons")
        return home_icons in xcursor_path or dot_icons in xcursor_path

    def get_active_themes(self) -> Dict[str, str]:
        """Returns dict of currently active theme names per type key."""
        active = {
            "gtk": DEFAULT_THEMES["gtk"],
            "icon": DEFAULT_THEMES["icon"],
            "cursor": DEFAULT_THEMES["cursor"],
            "shell": "",
            "wallpaper": ""
        }

        # Interface themes (gtk, icon, cursor)
        iface = self._get_settings(INTERFACE_SCHEMA)
        if iface:
            try:
                active["gtk"] = iface.get_string("gtk-theme")
                active["icon"] = iface.get_string("icon-theme")
                active["cursor"] = iface.get_string("cursor-theme")
            except Exception as e:
                logger.warning(f"Error reading interface settings: {e}")

        # Shell theme
        user_theme = self._get_settings(USER_THEME_SCHEMA)
        if user_theme:
            try:
                active["shell"] = user_theme.get_string("name")
            except Exception as e:
                logger.warning(f"Error reading user-theme settings: {e}")

        # Wallpaper
        bg = self._get_settings(BACKGROUND_SCHEMA)
        if bg:
            try:
                active["wallpaper"] = bg.get_string("picture-uri")
            except Exception as e:
                logger.warning(f"Error reading background settings: {e}")

        return active

    def _update_gtk4_config(self, theme_name: str):
        """
        Symlinks or updates GTK4 configuration (~/.config/gtk-4.0/) if theme provides GTK4 styles.
        This enables GTK4 and Libadwaita applications to render with the selected GTK theme.
        """
        gtk4_config_dir = os.path.join(self.home_dir, ".config", "gtk-4.0")
        target_css = os.path.join(gtk4_config_dir, "gtk.css")
        target_assets = os.path.join(gtk4_config_dir, "assets")

        # Candidate theme locations
        search_dirs = [
            os.path.join(self.home_dir, ".local", "share", "themes", theme_name),
            os.path.join(self.home_dir, ".themes", theme_name),
            os.path.join("/usr", "share", "themes", theme_name)
        ]

        source_gtk4_dir = None
        for d in search_dirs:
            candidate = os.path.join(d, "gtk-4.0")
            if os.path.isdir(candidate):
                source_gtk4_dir = candidate
                break

        if source_gtk4_dir and os.path.isfile(os.path.join(source_gtk4_dir, "gtk.css")):
            os.makedirs(gtk4_config_dir, exist_ok=True)

            src_css = os.path.join(source_gtk4_dir, "gtk.css")
            src_assets = os.path.join(source_gtk4_dir, "assets")

            # Update gtk.css
            try:
                if os.path.lexists(target_css):
                    os.remove(target_css)
                os.symlink(src_css, target_css)
            except Exception as e:
                logger.warning(f"Could not symlink GTK4 CSS: {e}")

            # Update assets if present
            if os.path.isdir(src_assets):
                try:
                    if os.path.lexists(target_assets):
                        if os.path.islink(target_assets):
                            os.remove(target_assets)
                        else:
                            shutil.rmtree(target_assets)
                    os.symlink(src_assets, target_assets)
                except Exception as e:
                    logger.warning(f"Could not symlink GTK4 assets: {e}")
        else:
            # If theme has no gtk-4.0 or reverting to default, clean up motif-managed symlinks
            if os.path.islink(target_css):
                try:
                    os.remove(target_css)
                except Exception:
                    pass
            if os.path.islink(target_assets):
                try:
                    os.remove(target_assets)
                except Exception:
                    pass

    def set_theme(self, type_key: str, value: str) -> bool:
        """
        Sets a theme for a given type key.
        Applies changes live using Gio.Settings and logs rollback history.
        """
        schema_id = None
        key = None
        target_value = value

        if type_key == "gtk":
            schema_id, key = INTERFACE_SCHEMA, "gtk-theme"
        elif type_key == "icon":
            schema_id, key = INTERFACE_SCHEMA, "icon-theme"
        elif type_key == "cursor":
            schema_id, key = INTERFACE_SCHEMA, "cursor-theme"
        elif type_key == "shell":
            schema_id, key = USER_THEME_SCHEMA, "name"
        elif type_key == "wallpaper":
            schema_id, key = BACKGROUND_SCHEMA, "picture-uri"
            if not target_value.startswith("file://") and target_value.startswith("/"):
                target_value = f"file://{target_value}"
        else:
            logger.error(f"Unknown theme type key: {type_key}")
            return False

        settings = self._get_settings(schema_id)
        if not settings:
            logger.error(f"GSettings schema '{schema_id}' not available.")
            return False

        try:
            old_value = settings.get_string(key)

            # Apply change in GSettings
            success = settings.set_string(key, target_value)
            Gio.Settings.sync()

            if success or old_value != target_value:
                if old_value != target_value:
                    self._history.append((schema_id, key, old_value, target_value))
                logger.info(f"Applied {type_key} theme '{target_value}' (was '{old_value}')")

                # If setting wallpaper picture-uri, also update picture-uri-dark
                if type_key == "wallpaper":
                    try:
                        settings.set_string("picture-uri-dark", target_value)
                        Gio.Settings.sync()
                    except Exception:
                        pass

                # If setting GTK theme, link GTK4 files for Libadwaita apps
                if type_key == "gtk":
                    self._update_gtk4_config(value)

                # If setting cursor theme on X11, optionally notify xsetroot
                if type_key == "cursor" and shutil.which("xsetroot"):
                    try:
                        subprocess.run(["xsetroot", "-cursor_name", "left_ptr"], check=False)
                    except Exception:
                        pass

                return True
        except Exception as e:
            logger.error(f"Failed to set {type_key} theme to '{target_value}': {e}")

        return False

    def revert_to_default(self, type_key: str) -> bool:
        """
        Reverts a theme type key to default value (Adwaita or empty string).
        Used before deleting active theme files to prevent broken desktop pointers.
        """
        default_val = DEFAULT_THEMES.get(type_key, "Adwaita")
        return self.set_theme(type_key, default_val)

    def revert_last_change(self) -> Tuple[bool, str]:
        """
        Rolls back the last applied theme change.
        Returns (success_boolean, description_message).
        """
        if not self._history:
            return False, "No previous changes to revert."

        schema_id, key, old_val, new_val = self._history.pop()
        settings = self._get_settings(schema_id)
        if not settings:
            return False, f"Schema '{schema_id}' is no longer available."

        try:
            settings.set_string(key, old_val)
            Gio.Settings.sync()

            # Clean up or restore GTK4 link if reverting GTK theme
            if key == "gtk-theme":
                self._update_gtk4_config(old_val)

            msg = f"Reverted key '{key}' from '{new_val}' back to '{old_val}'."
            logger.info(msg)
            return True, msg
        except Exception as e:
            return False, f"Failed to revert '{key}': {e}"

