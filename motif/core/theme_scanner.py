"""
Theme scanner: scans local and system theme directories to detect installed themes.
"""
import os
import configparser
import logging
from typing import List, Dict, Optional

from motif.api.models import InstalledTheme

logger = logging.getLogger(__name__)

class ThemeScanner:
    def __init__(self, custom_dirs: Optional[List[str]] = None):
        self.home_dir = os.path.expanduser("~")
        if custom_dirs:
            self.search_dirs = custom_dirs
        else:
            self.search_dirs = [
                os.path.join(self.home_dir, ".local", "share", "themes"),
                os.path.join(self.home_dir, ".local", "share", "icons"),
                os.path.join(self.home_dir, ".themes"),
                os.path.join(self.home_dir, ".icons"),
                "/usr/share/themes",
                "/usr/share/icons",
                os.path.join(self.home_dir, ".local", "share", "backgrounds"),
            ]

    @staticmethod
    def _parse_index_theme(index_path: str) -> Dict[str, any]:
        """Parses index.theme INI file and returns dictionary of metadata."""
        meta = {"Name": "", "Comment": "", "Inherits": "", "Hidden": False, "Directories": ""}
        if not os.path.isfile(index_path):
            return meta

        parser = configparser.ConfigParser(interpolation=None)
        try:
            with open(index_path, "r", encoding="utf-8", errors="ignore") as f:
                parser.read_file(f)
            # Usually [Desktop Entry] or [Icon Theme]
            section = None
            if parser.has_section("Icon Theme"):
                section = "Icon Theme"
            elif parser.has_section("Desktop Entry"):
                section = "Desktop Entry"
            elif parser.sections():
                section = parser.sections()[0]

            if section:
                meta["Name"] = parser.get(section, "Name", fallback="")
                meta["Comment"] = parser.get(section, "Comment", fallback="")
                meta["Inherits"] = parser.get(section, "Inherits", fallback="")
                meta["Directories"] = parser.get(section, "Directories", fallback="")
                hidden_str = parser.get(section, "Hidden", fallback=parser.get(section, "NoDisplay", fallback="false")).lower()
                meta["Hidden"] = hidden_str in ("true", "1", "yes")
        except Exception as e:
            logger.warning(f"Error parsing {index_path}: {e}")
        return meta

    def scan_all(self, active_themes: Optional[Dict[str, str]] = None) -> List[InstalledTheme]:
        """
        Scans all theme search directories and returns list of InstalledTheme objects.
        active_themes parameter map: {'gtk': 'Yaru', 'icon': 'Yaru', 'cursor': 'Yaru', 'shell': 'Yaru'}
        """
        active_themes = active_themes or {}
        installed_list: List[InstalledTheme] = []
        seen_keys = set()  # (type_key, theme_name) to avoid duplicates across user/system dirs

        for search_dir in self.search_dirs:
            if not os.path.exists(search_dir):
                continue

            is_user_dir = search_dir.startswith(self.home_dir)

            try:
                entries = os.listdir(search_dir)
            except Exception as e:
                logger.warning(f"Could not read directory {search_dir}: {e}")
                continue

            for entry in entries:
                if entry.startswith("."):
                    continue

                full_path = os.path.join(search_dir, entry)

                # Special handling for wallpaper backgrounds directory
                if "backgrounds" in search_dir:
                    if os.path.isfile(full_path) and any(full_path.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".svg", ".webp"]):
                        active_bg = active_themes.get("wallpaper", "").replace("file://", "")
                        is_bg_active = (active_bg == full_path)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            installed_list.append(InstalledTheme(
                                name=entry,
                                path=full_path,
                                type_key="wallpaper",
                                is_active=is_bg_active,
                                is_motif_managed=is_user_dir,
                                version="1.0"
                            ))
                    continue

                if not os.path.isdir(full_path):
                    continue

                index_path = os.path.join(full_path, "index.theme")
                meta = self._parse_index_theme(index_path)
                has_index = os.path.isfile(index_path)

                sub_files = os.listdir(full_path)
                has_cursors = "cursors" in sub_files and os.path.isdir(os.path.join(full_path, "cursors"))
                has_gtk3 = ("gtk-3.0" in sub_files and os.path.isdir(os.path.join(full_path, "gtk-3.0"))) and not os.path.isfile(os.path.join(full_path, "gtk-3.0", "gtk-keys.css"))
                has_gtk4 = "gtk-4.0" in sub_files and os.path.isdir(os.path.join(full_path, "gtk-4.0"))
                has_shell = ("gnome-shell" in sub_files and os.path.isdir(os.path.join(full_path, "gnome-shell"))) or os.path.isfile(os.path.join(full_path, "gnome-shell.css"))

                # Classify theme type
                # 1. Cursor theme
                if has_cursors:
                    key = ("cursor", entry)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        installed_list.append(InstalledTheme(
                            name=entry,
                            path=full_path,
                            type_key="cursor",
                            is_active=(active_themes.get("cursor") == entry),
                            is_motif_managed=is_user_dir,
                            comment=meta.get("Comment", "")
                        ))
                    continue

                variants = []
                if has_gtk3:
                    variants.append("GTK3")
                if has_gtk4:
                    variants.append("GTK4")
                if has_shell:
                    variants.append("Shell")

                # 2. GTK theme entry
                if has_gtk3 or has_gtk4:
                    gtk_key = ("gtk", entry)
                    if gtk_key not in seen_keys:
                        seen_keys.add(gtk_key)
                        installed_list.append(InstalledTheme(
                            name=entry,
                            path=full_path,
                            type_key="gtk",
                            is_active=(active_themes.get("gtk") == entry),
                            is_motif_managed=is_user_dir,
                            comment=meta.get("Comment", ""),
                            variants=variants
                        ))

                # 3. Shell theme entry if gnome-shell is supported
                if has_shell:
                    shell_key = ("shell", entry)
                    if shell_key not in seen_keys:
                        seen_keys.add(shell_key)
                        installed_list.append(InstalledTheme(
                            name=entry,
                            path=full_path,
                            type_key="shell",
                            is_active=(active_themes.get("shell") == entry),
                            is_motif_managed=is_user_dir,
                            comment=meta.get("Comment", ""),
                            variants=variants
                        ))

                # 4. Icon theme (must have index.theme, not hidden, has directories or inherits/name, no cursors/gtk/shell)
                if has_index and not meta.get("Hidden") and not (has_gtk3 or has_gtk4 or has_shell or has_cursors):
                    if meta.get("Directories") or (meta.get("Name") and meta.get("Inherits")):
                        key = ("icon", entry)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            installed_list.append(InstalledTheme(
                                name=entry,
                                path=full_path,
                                type_key="icon",
                                is_active=(active_themes.get("icon") == entry),
                                is_motif_managed=is_user_dir,
                                comment=meta.get("Comment", "")
                            ))

        return installed_list
