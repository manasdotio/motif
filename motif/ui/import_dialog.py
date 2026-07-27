"""
Import from GitHub / URL Dialog: interactive modal window for downloading and customizing themes from GitHub or direct URLs.
"""
import os
import logging
import threading
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from motif.core.github_installer import GitHubInstaller
from motif.core.installer import InstallationError

logger = logging.getLogger(__name__)

COLOR_VARIANTS = ["Default", "Dark", "Light", "Darker"]
ACCENT_COLORS = ["Default", "Blue", "Purple", "Pink", "Red", "Orange", "Green", "Teal", "Grey"]
STYLE_VARIANTS = ["Default", "Compact"]

CATEGORY_MAP = {
    0: ("gtk", "GTK Theme"),
    1: ("shell", "Shell Theme"),
    2: ("icon", "Icon Theme"),
    3: ("cursor", "Cursor Theme"),
    4: ("wallpaper", "Wallpaper")
}

class ImportDialog(Adw.Window):
    def __init__(self, transient_for=None, on_installed_callback=None, on_toast_callback=None):
        super().__init__()

        self.set_title("Import Theme from GitHub / URL")
        self.set_modal(True)
        self.set_default_size(540, 600)
        self.set_resizable(False)

        if transient_for:
            self.set_transient_for(transient_for)

        self.on_installed_callback = on_installed_callback
        self.on_toast_callback = on_toast_callback
        self.gh_installer = GitHubInstaller()

        self.color_variants = list(COLOR_VARIANTS)
        self.accent_variants = list(ACCENT_COLORS)
        self.style_variants = list(STYLE_VARIANTS)

        # Main Layout
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # HeaderBar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        title_widget = Adw.WindowTitle(title="Import Theme", subtitle="Step-by-step Interactive Customization")
        header.set_title_widget(title_widget)
        content_box.append(header)

        # Preferences Page & Groups
        page = Adw.PreferencesPage()

        # 1. Source Group
        source_group = Adw.PreferencesGroup()
        source_group.set_title("Theme Source & Detection")
        source_group.set_description("Enter a canonical GitHub URL (e.g. https://github.com/vinceliuice/Orchis-theme) or direct archive link")

        self.url_row = Adw.EntryRow()
        self.url_row.set_title("GitHub Repository / Archive URL")
        self.url_row.set_text("")
        source_group.add(self.url_row)

        self.analyze_btn = Gtk.Button(label="Analyze Theme Options")
        self.analyze_btn.set_valign(Gtk.Align.CENTER)
        self.analyze_btn.add_css_class("flat")
        self.analyze_btn.add_css_class("accent")
        self.analyze_btn.connect("clicked", self._on_analyze_clicked)
        self.url_row.add_suffix(self.analyze_btn)

        self.name_row = Adw.EntryRow()
        self.name_row.set_title("Custom Theme Name (Optional)")
        source_group.add(self.name_row)

        # Category Selector
        cat_model = Gtk.StringList.new(["GTK Theme", "Shell Theme", "Icon Theme", "Cursor Theme", "Wallpaper"])
        self.category_row = Adw.ComboRow()
        self.category_row.set_title("Category")
        self.category_row.set_model(cat_model)
        self.category_row.set_selected(0)
        source_group.add(self.category_row)

        page.add(source_group)

        # 2. Customization Options Expander
        custom_group = Adw.PreferencesGroup()
        custom_group.set_title("Step-by-Step Customization Options")
        custom_group.set_description("Options detected dynamically from repository installer")

        custom_expander = Adw.ExpanderRow()
        custom_expander.set_title("Tailored Theme Choices")
        custom_expander.set_subtitle("Color flavor, Accent color, Size, Libadwaita")
        custom_expander.set_expanded(True)

        # Color Variant
        self.color_model = Gtk.StringList.new(self.color_variants)
        self.color_row = Adw.ComboRow()
        self.color_row.set_title("Color Scheme / Flavor")
        self.color_row.set_model(self.color_model)
        self.color_row.set_selected(0)
        custom_expander.add_row(self.color_row)

        # Accent Color
        self.accent_model = Gtk.StringList.new(self.accent_variants)
        self.accent_row = Adw.ComboRow()
        self.accent_row.set_title("Accent Color")
        self.accent_row.set_model(self.accent_model)
        self.accent_row.set_selected(0)
        custom_expander.add_row(self.accent_row)

        # Style Variant
        self.style_model = Gtk.StringList.new(self.style_variants)
        self.style_row = Adw.ComboRow()
        self.style_row.set_title("Size / Style Variant")
        self.style_row.set_model(self.style_model)
        self.style_row.set_selected(0)
        custom_expander.add_row(self.style_row)

        # Libadwaita Switch
        self.libadwaita_row = Adw.SwitchRow()
        self.libadwaita_row.set_title("Patch Libadwaita Applications")
        self.libadwaita_row.set_subtitle("Pass -l flag to patch GTK4/Adwaita apps")
        self.libadwaita_row.set_active(False)
        custom_expander.add_row(self.libadwaita_row)

        # Custom Tweaks & Flags Entry Row
        self.custom_flags_row = Adw.EntryRow()
        self.custom_flags_row.set_title("Advanced Custom Tweaks & Extra Flags")
        self.custom_flags_row.set_text("")
        custom_expander.add_row(self.custom_flags_row)

        custom_group.add(custom_expander)
        page.add(custom_group)

        # 3. Status & Progress Group
        self.progress_group = Adw.PreferencesGroup()
        self.progress_group.set_title("Installation Status")

        self.status_label = Gtk.Label(label="Paste URL and click 'Analyze Theme Options' or 'Install Theme'")
        self.status_label.set_xalign(0.0)
        self.status_label.set_margin_start(12)
        self.status_label.set_margin_end(12)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_margin_start(12)
        self.progress_bar.set_margin_end(12)
        self.progress_bar.set_margin_bottom(12)

        self.progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.progress_box.append(self.status_label)
        self.progress_box.append(self.progress_bar)

        self.progress_group.add(self.progress_box)
        page.add(self.progress_group)

        content_box.append(page)

        # Action Buttons Box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_margin_start(16)
        button_box.set_margin_end(16)
        button_box.set_margin_top(12)
        button_box.set_margin_bottom(16)

        self.cancel_btn = Gtk.Button(label="Cancel")
        self.cancel_btn.set_hexpand(True)
        self.cancel_btn.connect("clicked", lambda b: self.close())
        button_box.append(self.cancel_btn)

        self.install_btn = Gtk.Button(label="Install Theme")
        self.install_btn.set_hexpand(True)
        self.install_btn.add_css_class("suggested-action")
        self.install_btn.connect("clicked", self._on_install_clicked)
        button_box.append(self.install_btn)

        content_box.append(button_box)

        self.set_content(content_box)

    def _on_analyze_clicked(self, btn):
        url = self.url_row.get_text().strip()
        if not url:
            self.status_label.set_text("Error: Please enter a GitHub repository URL first")
            return

        self.analyze_btn.set_sensitive(False)
        self.status_label.set_text("Analyzing repository installer options...")
        self.progress_bar.set_fraction(0.3)

        thread = threading.Thread(target=self._run_analysis, args=(url,), daemon=True)
        thread.start()

    def _run_analysis(self, url: str):
        opts = self.gh_installer.inspect_repository_options(url)
        GLib.idle_add(self._on_analysis_success, opts)

    def _on_analysis_success(self, opts: dict):
        self.analyze_btn.set_sensitive(True)
        self.progress_bar.set_fraction(0.0)

        if not opts.get("has_script"):
            self.status_label.set_text("No custom installer script detected. Using standard extraction.")
            return

        # Update Color Options
        if opts.get("colors"):
            formatted_colors = ["Default"] + [c.capitalize() for c in opts["colors"]]
            self.color_variants = formatted_colors
            self.color_row.set_model(Gtk.StringList.new(formatted_colors))
            self.color_row.set_selected(0)
            colors_preview = ", ".join(formatted_colors[1:6])
            if len(formatted_colors) > 6:
                colors_preview += "..."
            self.color_row.set_subtitle(f"Loaded {len(opts['colors'])} choices ({colors_preview})")

        # Update Accent Options
        if opts.get("accents"):
            formatted_accents = ["Default"] + [a.capitalize() for a in opts["accents"]]
            self.accent_variants = formatted_accents
            self.accent_row.set_model(Gtk.StringList.new(formatted_accents))
            self.accent_row.set_selected(0)
            accents_preview = ", ".join(formatted_accents[1:6])
            if len(formatted_accents) > 6:
                accents_preview += "..."
            self.accent_row.set_subtitle(f"Loaded {len(opts['accents'])} accents ({accents_preview})")

        # Update Styles
        if opts.get("styles"):
            formatted_styles = ["Default"] + [s.capitalize() for s in opts["styles"]]
            self.style_variants = formatted_styles
            self.style_row.set_model(Gtk.StringList.new(formatted_styles))
            self.style_row.set_selected(0)
            self.style_row.set_subtitle(f"Loaded {len(opts['styles'])} styles")

        if opts.get("has_libadwaita"):
            self.libadwaita_row.set_active(True)

        # Update Tweaks & Flags Hint
        if opts.get("tweaks"):
            tweaks_list = ", ".join(opts["tweaks"])
            self.custom_flags_row.set_title(f"Custom Tweaks ({tweaks_list})")
            if opts.get("tweaks_hint"):
                hint_str = opts["tweaks_hint"]
                # Provide quick insert button if not already present
                insert_btn = Gtk.Button(label="Insert Example")
                insert_btn.set_valign(Gtk.Align.CENTER)
                insert_btn.add_css_class("flat")
                insert_btn.connect("clicked", lambda b: self.custom_flags_row.set_text(hint_str))
                self.custom_flags_row.add_suffix(insert_btn)
        else:
            self.custom_flags_row.set_title("Advanced Custom Tweaks & Extra Flags")

        repo_name = opts.get("repo_name", "Theme")
        num_colors = len(opts.get("colors", []))
        num_accents = len(opts.get("accents", []))
        self.status_label.set_text(f"Detected '{repo_name}' with {num_colors} flavors, {num_accents} accents & tweaks!")

    def _on_install_clicked(self, btn):
        url = self.url_row.get_text().strip()
        if not url:
            self.status_label.set_text("Error: Please enter a valid GitHub or direct URL")
            return

        cat_idx = self.category_row.get_selected()
        type_key, cat_name = CATEGORY_MAP.get(cat_idx, ("gtk", "GTK Theme"))

        custom_name = self.name_row.get_text().strip()
        
        color_sel = self.color_row.get_selected()
        color = self.color_variants[color_sel].lower() if color_sel < len(self.color_variants) else "default"

        accent_sel = self.accent_row.get_selected()
        accent = self.accent_variants[accent_sel].lower() if accent_sel < len(self.accent_variants) else "default"

        style_sel = self.style_row.get_selected()
        style = self.style_variants[style_sel].lower() if style_sel < len(self.style_variants) else "default"

        libadwaita = self.libadwaita_row.get_active()
        custom_flags = self.custom_flags_row.get_text().strip()

        # Disable controls during install
        self.install_btn.set_sensitive(False)
        self.url_row.set_sensitive(False)
        self.progress_bar.set_fraction(0.05)
        self.status_label.set_text("Starting installation...")

        # Run background thread
        thread = threading.Thread(
            target=self._run_installation,
            args=(url, type_key, custom_name, color, accent, style, libadwaita, custom_flags),
            daemon=True
        )
        thread.start()

    def _run_installation(self, url, type_key, custom_name, color, accent, style, libadwaita, custom_flags):
        def progress_cb(msg: str, pct: float):
            GLib.idle_add(self._update_progress_ui, msg, pct)

        try:
            installed_path = self.gh_installer.install(
                url=url,
                type_key=type_key,
                custom_name=custom_name,
                color=color,
                accent=accent,
                style=style,
                libadwaita=libadwaita,
                custom_flags=custom_flags,
                progress_cb=progress_cb
            )

            GLib.idle_add(self._on_success, installed_path)
        except Exception as e:
            logger.error(f"Import installation error: {e}")
            GLib.idle_add(self._on_failure, str(e))

    def _update_progress_ui(self, msg: str, pct: float):
        self.status_label.set_text(msg)
        self.progress_bar.set_fraction(pct)

    def _on_success(self, path: str):
        theme_name = os.path.basename(path)
        msg = f"Successfully installed '{theme_name}' from GitHub/URL!"
        logger.info(msg)

        if self.on_toast_callback:
            self.on_toast_callback(msg)

        if self.on_installed_callback:
            self.on_installed_callback()

        self.close()

    def _on_failure(self, error_msg: str):
        self.status_label.set_text(f"Error: {error_msg}")
        self.progress_bar.set_fraction(0.0)
        self.install_btn.set_sensitive(True)
        self.url_row.set_sensitive(True)
