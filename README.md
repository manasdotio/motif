# Motif — GNOME Theme Manager 🎨

**Motif** is a native GTK4 + libadwaita desktop application for GNOME that brings a smooth, one-click experience to **browsing, downloading, applying, and managing** GTK themes, GNOME Shell themes, Icon themes, Cursor themes, and Wallpapers — with zero manual file copying or terminal commands required.

---

## Features

- 🏪 **Store Tab**:
  - Categories for **GTK Themes, Shell Themes, Icon Themes, Cursor Themes, and Wallpapers**.
  - Live search with 300ms debouncing.
  - Sorting by Rating, Downloads, Newest, or Name.
  - Infinite scroll pagination.
  - Detail view with screenshot gallery, description, changelog, and multi-file package selector.
- 📦 **Download & Installation Engine**:
  - Open Collaboration Services (OCS) API v1 client for `gnome-look.org`.
  - Format validation before extraction (`tar.xz`, `tar.gz`, `zip`).
  - Auto-detection of nested root directories.
  - Per-category structural validation (e.g. enforcing presence of `cursors/` and `index.theme` for cursor themes).
  - Clean placement in `~/.local/share/themes`, `~/.local/share/icons`, or `~/.local/share/backgrounds`.
- 🐙 **GitHub & Direct URL Theme Installer**:
  - Paste any GitHub repository link (e.g. `https://github.com/vinceliuice/Orchis-theme`) or direct archive URL (`.tar.xz`, `.zip`).
  - Interactive Customization Options dialog: Color Scheme (Dark, Light, Darker), Accent Color (Blue, Purple, Pink, Teal, etc.), Compact/Standard size mode, and Libadwaita application patch toggles.
  - Automatically executes repo `./install.sh` scripts safely with user parameters or extracts archive files.
- ⚙️ **Direct Live GSettings Application**:
  - Direct `Gio.Settings` integration (no `gsettings` CLI shelling out).
  - Radio selector for active theme.
  - Automatic reversion of active theme to `Adwaita` before deleting files.
  - Built-in Rollback ("Revert Last Change") history.
  - Inline alerts for User Themes extension and Wayland `XCURSOR_PATH`.
- 🔍 **Local Theme Scanner**:
  - Scans `~/.themes`, `~/.icons`, `~/.local/share/themes`, `~/.local/share/icons`, `/usr/share/themes`, `/usr/share/icons` on launch.

---

## Directory Architecture

```
themes-manager/
├── motif/
│   ├── main.py                  # Adw.Application entry point
│   ├── window.py                 # Main AdwApplicationWindow, ViewStack & ToastOverlay
│   ├── api/
│   │   ├── ocs_client.py         # OCS API v1 Client (Search, Details, Download)
│   │   └── models.py             # Dataclasses (ThemeItem, Category, InstalledTheme)
│   ├── core/
│   │   ├── installer.py          # Download -> Validate -> Extract -> Flatten -> Place
│   │   ├── theme_scanner.py      # Local & System Theme Scanner
│   │   ├── gsettings_manager.py  # Direct Gio.Settings Wrapper & Rollback
│   │   └── validators.py         # Structural Validation Rules
│   ├── ui/
│   │   ├── store_view.py         # Store Grid, Categories, Search & Infinite Scroll
│   │   ├── detail_view.py        # Item Details, Screenshot Gallery Carousel, Install
│   │   ├── installed_view.py     # Installed List, Active Selector, Delete & Alerts
│   │   └── widgets/
│   │       └── theme_card.py     # Reusable GtkFlowBox Theme Card Widget
│   └── data/
│       └── org.gnome.Motif.gschema.xml   # GSettings schema
├── tests/                        # Unit tests suite (Pytest)
├── org.gnome.Motif.json        # Flatpak manifest
├── org.gnome.Motif.desktop     # Desktop Entry
├── org.gnome.Motif.svg         # App Icon
└── pyproject.toml
```

---

## Running Locally

### Requirements
- Python 3.11+
- GTK4 & Libadwaita (PyGObject)
- `httpx`

### Commands
```bash
# Set up virtual environment with system PyGObject bindings
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e .

# Run unit tests
PYTHONPATH=. .venv/bin/pytest

# Run Application
PYTHONPATH=. .venv/bin/python3 -m motif.main
```

---

## Packaging & Building Flatpak

```bash
# Build Flatpak package
flatpak-builder --user --install --force-clean build-dir org.gnome.Motif.json

# Run Flatpak
flatpak run org.gnome.Motif
```
