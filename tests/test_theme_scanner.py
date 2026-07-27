"""
Unit tests for Theme Scanner.
"""
import os
import tempfile
import pytest

from motif.core.theme_scanner import ThemeScanner

def test_theme_scanner_custom_dirs():
    with tempfile.TemporaryDirectory() as tmpdir:
        themes_dir = os.path.join(tmpdir, "themes")
        icons_dir = os.path.join(tmpdir, "icons")
        os.makedirs(themes_dir)
        os.makedirs(icons_dir)

        # Create GTK theme
        gtk_dir = os.path.join(themes_dir, "CustomGTK")
        os.makedirs(os.path.join(gtk_dir, "gtk-3.0"))
        with open(os.path.join(gtk_dir, "index.theme"), "w") as f:
            f.write("[Desktop Entry]\nName=CustomGTK\nComment=Test GTK Theme")

        # Create Cursor theme
        cursor_dir = os.path.join(icons_dir, "CustomCursor")
        os.makedirs(os.path.join(cursor_dir, "cursors"))
        with open(os.path.join(cursor_dir, "index.theme"), "w") as f:
            f.write("[Icon Theme]\nName=CustomCursor\nComment=Test Cursor Theme")

        scanner = ThemeScanner(custom_dirs=[themes_dir, icons_dir])
        active = {"gtk": "CustomGTK", "cursor": "OtherCursor"}

        results = scanner.scan_all(active_themes=active)
        assert len(results) == 2

        gtk_item = next(r for r in results if r.name == "CustomGTK")
        assert gtk_item.type_key == "gtk"
        assert gtk_item.is_active is True

        cursor_item = next(r for r in results if r.name == "CustomCursor")
        assert cursor_item.type_key == "cursor"
        assert cursor_item.is_active is False

def test_theme_scanner_filters_hidden_and_keybindings():
    with tempfile.TemporaryDirectory() as tmpdir:
        themes_dir = os.path.join(tmpdir, "themes")
        icons_dir = os.path.join(tmpdir, "icons")
        os.makedirs(themes_dir)
        os.makedirs(icons_dir)

        # Keybinding theme (Default / Emacs style with gtk-keys.css)
        keybindings_dir = os.path.join(themes_dir, "Emacs")
        os.makedirs(os.path.join(keybindings_dir, "gtk-3.0"))
        with open(os.path.join(keybindings_dir, "gtk-3.0", "gtk-keys.css"), "w") as f:
            f.write("binding-set emacs { ... }")

        # Hidden icon theme (AdwaitaLegacy / hicolor style)
        hidden_icon_dir = os.path.join(icons_dir, "HiddenIcons")
        os.makedirs(hidden_icon_dir)
        with open(os.path.join(hidden_icon_dir, "index.theme"), "w") as f:
            f.write("[Icon Theme]\nName=HiddenIcons\nHidden=true\nDirectories=16x16/apps")

        # Directory without index.theme (e.g. hicolor app icon folder)
        no_index_dir = os.path.join(icons_dir, "no_index_folder")
        os.makedirs(no_index_dir)

        # Valid icon theme
        valid_icon_dir = os.path.join(icons_dir, "ValidIconTheme")
        os.makedirs(valid_icon_dir)
        with open(os.path.join(valid_icon_dir, "index.theme"), "w") as f:
            f.write("[Icon Theme]\nName=ValidIconTheme\nDirectories=16x16/apps")

        scanner = ThemeScanner(custom_dirs=[themes_dir, icons_dir])
        results = scanner.scan_all()

        names = [r.name for r in results]
        assert "Emacs" not in names
        assert "HiddenIcons" not in names
        assert "no_index_folder" not in names
        assert "ValidIconTheme" in names

