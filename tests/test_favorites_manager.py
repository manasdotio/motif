"""
Unit tests for FavoritesManager.
"""
import os
import tempfile
import pytest

from motif.api.models import ThemeItem, DownloadFile
from motif.core.favorites_manager import FavoritesManager

@pytest.fixture
def temp_config_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def sample_theme():
    return ThemeItem(
        id="999",
        name="Orchis Dark GTK",
        author="vinceliuice",
        version="2.0",
        summary="Sleek theme",
        description="Full description",
        changelog="v2 release",
        category_id="135",
        category_name="GTK Themes",
        type_key="gtk",
        score=98,
        downloads=15000,
        created="2026-01-01",
        preview_urls=["https://example.com/preview.png"],
        download_files=[DownloadFile(id="999-1", name="orchis.tar.xz", url="https://example.com/orchis.tar.xz")]
    )

def test_favorites_manager_add_remove(temp_config_dir, sample_theme):
    mgr = FavoritesManager(config_dir=temp_config_dir)
    assert not mgr.is_favorite("999")
    assert len(mgr.get_favorites()) == 0

    mgr.add_favorite(sample_theme)
    assert mgr.is_favorite("999")
    assert len(mgr.get_favorites()) == 1
    assert mgr.get_favorites()[0].name == "Orchis Dark GTK"

    mgr.remove_favorite("999")
    assert not mgr.is_favorite("999")
    assert len(mgr.get_favorites()) == 0

def test_favorites_manager_toggle(temp_config_dir, sample_theme):
    mgr = FavoritesManager(config_dir=temp_config_dir)
    res1 = mgr.toggle_favorite(sample_theme)
    assert res1 is True
    assert mgr.is_favorite("999")

    res2 = mgr.toggle_favorite(sample_theme)
    assert res2 is False
    assert not mgr.is_favorite("999")

def test_favorites_manager_persistence(temp_config_dir, sample_theme):
    mgr1 = FavoritesManager(config_dir=temp_config_dir)
    mgr1.add_favorite(sample_theme)

    # Reload from disk in a second instance
    mgr2 = FavoritesManager(config_dir=temp_config_dir)
    assert mgr2.is_favorite("999")
    favs = mgr2.get_favorites()
    assert len(favs) == 1
    assert favs[0].id == "999"
    assert favs[0].name == "Orchis Dark GTK"
    assert favs[0].type_key == "gtk"
    assert len(favs[0].download_files) == 1
