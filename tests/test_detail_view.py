import pytest
from unittest.mock import MagicMock
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from motif.ui.detail_view import DetailView, format_relative_time, format_version


def test_format_version():
    assert format_version("0.4.1") == "version v0.4.1"
    assert format_version("v1.2") == "version v1.2"
    assert format_version("") == "version v1.0"


def test_format_relative_time():
    assert "ago" in format_relative_time("2023-05-10T12:00:00Z")
    assert format_relative_time("") == "recently"


def test_detail_view_on_previews_finished():
    mock_ocs = MagicMock()
    mock_installer = MagicMock()
    view = DetailView(ocs_client=mock_ocs, installer=mock_installer)
    
    view.preview_textures = ["tex1", "tex2"]
    # Verify _on_previews_finished executes without AttributeError
    view._on_previews_finished()
    assert view.dots.get_visible() is True
    assert view.nav_fullscreen.get_visible() is True


def test_detail_view_links_row():
    from motif.api.models import ThemeItem
    mock_ocs = MagicMock()
    mock_installer = MagicMock()
    view = DetailView(ocs_client=mock_ocs, installer=mock_installer)

    item = ThemeItem(
        id="123",
        name="Test Theme",
        author="Tester",
        version="1.0",
        summary="Summary",
        description="Description",
        changelog="",
        category_id="1",
        category_name="GTK Theme",
        type_key="gtk",
        score=90,
        downloads=500,
        created="2024-01-01",
        source_url="https://github.com/test/repo",
        detail_page="https://pling.com/p/123",
        homepage="https://example.com"
    )

    view.set_item(item)
    assert view.links_scroll.get_visible() is True
    assert view.source_btn.get_visible() is True
    assert view.source_btn.get_uri() == "https://github.com/test/repo"
    assert "GitHub:" in view.source_btn.get_label()
    assert view.store_link_btn.get_visible() is True
    assert view.store_link_btn.get_uri() == "https://pling.com/p/123"
    assert view.homepage_btn.get_visible() is True
    assert view.homepage_btn.get_uri() == "https://example.com"

