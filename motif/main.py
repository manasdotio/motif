"""
Motif application entry point.
"""
import sys
import os
import logging
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk

from motif.window import MotifWindow

logger = logging.getLogger(__name__)

def load_application_css():
    css_data = """
    .theme-card {
        min-width: 210px;
        transition: transform 150ms ease;
    }
    .theme-card:hover {
        transform: translateY(-2px);
    }
    .theme-card .card {
        border-radius: 12px;
    }
    .thumbnail-area {
        background-color: rgba(0, 0, 0, 0.2);
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
    }
    .carousel-dot {
        min-width: 20px;
        min-height: 20px;
        padding: 0;
        margin: 2px;
    }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css_data.encode("utf-8"))
    display = Gdk.Display.get_default()
    if display:
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

class MotifApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="org.gnome.Motif",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        GLib.set_application_name("Motif")

    def do_startup(self):
        Adw.Application.do_startup(self)
        load_application_css()

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MotifWindow(application=self)
        win.present()

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    # Load custom compiled GSettings schema from package data directory if present
    schema_dir = os.path.join(os.path.dirname(__file__), "data")
    if os.path.isdir(schema_dir):
        source = Gio.SettingsSchemaSource.get_default()
        new_source = Gio.SettingsSchemaSource.new_from_directory(
            schema_dir, source, False
        )
        if new_source:
            # Inject schema directory into GSETTINGS_SCHEMA_DIR environment
            current_dirs = os.environ.get("GSETTINGS_SCHEMA_DIR", "")
            os.environ["GSETTINGS_SCHEMA_DIR"] = f"{schema_dir}:{current_dirs}" if current_dirs else schema_dir

    app = MotifApplication()
    try:
        return app.run(sys.argv)
    except KeyboardInterrupt:
        return 0

if __name__ == "__main__":
    sys.exit(main())
