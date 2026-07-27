"""
Unit tests for GSettings Manager.
"""
import pytest
from motif.core.gsettings_manager import GSettingsManager, DEFAULT_THEMES

def test_gsettings_manager_active_themes():
    gsm = GSettingsManager()
    active = gsm.get_active_themes()
    assert isinstance(active, dict)
    assert "gtk" in active
    assert "icon" in active
    assert "cursor" in active

def test_gsettings_manager_rollback_history():
    gsm = GSettingsManager()
    # Test empty rollback
    ok, msg = gsm.revert_last_change()
    assert ok is False

def test_user_themes_and_xcursor_checks():
    gsm = GSettingsManager()
    ext_enabled = gsm.is_user_themes_extension_enabled()
    assert isinstance(ext_enabled, bool)

    xcursor_ok = gsm.is_xcursor_path_configured()
    assert isinstance(xcursor_ok, bool)

def test_update_gtk4_config(tmp_path, monkeypatch):
    gsm = GSettingsManager()
    monkeypatch.setattr(gsm, "home_dir", str(tmp_path))

    # Create dummy GTK theme with gtk-4.0/gtk.css
    theme_dir = tmp_path / ".local" / "share" / "themes" / "TestGtkTheme" / "gtk-4.0"
    theme_dir.mkdir(parents=True)
    (theme_dir / "gtk.css").write_text("/* GTK4 styles */")

    gsm._update_gtk4_config("TestGtkTheme")

    target_css = tmp_path / ".config" / "gtk-4.0" / "gtk.css"
    assert target_css.exists()
    assert target_css.is_symlink()

    # Reverting to theme without gtk-4.0 removes symlink
    gsm._update_gtk4_config("NonExistentTheme")
    assert not target_css.exists()

