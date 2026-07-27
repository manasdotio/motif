"""
Unit tests for OCS API Client.
"""
import pytest
from unittest.mock import MagicMock, patch
from motif.api.ocs_client import OCSClient, OCSClientError
from motif.api.models import Category, ThemeItem

def test_strip_html():
    clean = OCSClient._strip_html("<p>Hello <b>World</b></p><br/>Next line")
    assert "Hello World" in clean
    assert "Next line" in clean
    assert "<p>" not in clean

def test_detect_type_key():
    assert OCSClient._detect_type_key("GTK 3.x Theme/Style", "135") == "gtk"
    assert OCSClient._detect_type_key("GNOME Shell Theme", "134") == "shell"
    assert OCSClient._detect_type_key("X11 Mouse Theme", "107") == "cursor"
    assert OCSClient._detect_type_key("KDE Icon Theme", "132") == "icon"
    assert OCSClient._detect_type_key("Wallpapers Gnome", "300") == "wallpaper"

def test_fetch_categories_live():
    """Live test connecting to gnome-look OCS API."""
    client = OCSClient()
    categories = client.fetch_categories()
    assert len(categories) > 0
    # Check that GTK, shell, icon, cursor types are represented
    type_keys = {c.type_key for c in categories}
    assert "gtk" in type_keys or "shell" in type_keys or "icon" in type_keys

def test_search_content_live():
    """Live search test fetching GTK themes."""
    client = OCSClient()
    items, total = client.search_content(category_type="gtk", sort_mode="relevance", page_size=5)
    assert total > 0
    assert len(items) > 0
    item = items[0]
    assert isinstance(item, ThemeItem)
    assert item.id != ""
    assert item.name != ""

def test_parse_theme_item():
    client = OCSClient()
    raw = {
        "id": "12345",
        "name": "<p>Test Theme</p>",
        "personid": "john_doe",
        "version": "1.2",
        "typeid": "135",
        "typename": "GTK 3.x Theme",
        "score": "95",
        "downloads": "1200",
        "summary": "Short summary",
        "description": "<p>Full description</p>",
        "previewpic1": "https://example.com/preview1.png",
        "downloadlink1": "https://example.com/theme.tar.xz",
        "downloadname1": "Theme.tar.xz",
        "downloadsize1": "102456"
    }
    item = client._parse_theme_item(raw)
    assert item.id == "12345"
    assert item.name == "Test Theme"
    assert item.author == "john_doe"
    assert item.type_key == "gtk"
    assert item.score == 95
    assert item.downloads == 1200
    assert len(item.preview_urls) == 1
    assert len(item.download_files) == 1
    assert item.download_files[0].url == "https://example.com/theme.tar.xz"
