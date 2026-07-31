<p align="center">
  <img src="io.github.manasdotio.motif.svg" width="128" height="128" alt="Motif Logo">
  <h1 align="center">Motif</h1>
  <p align="center"><b>Native GTK4 + Libadwaita Desktop Theme Manager for GNOME</b></p>
  <p align="center">
    <a href="https://github.com/manasdotio/motif/releases/latest"><img src="https://img.shields.io/github/v/release/manasdotio/motif?style=for-the-badge&color=3584e4" alt="Latest Release"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-blue.svg?style=for-the-badge&color=26a269" alt="License GPL-3.0"></a>
    <a href="https://github.com/flathub/flathub/pulls"><img src="https://img.shields.io/badge/Flathub-Pending-orange.svg?style=for-the-badge&logo=flatpak" alt="Flathub Status"></a>
  </p>
</p>

---

**Motif** is a modern GTK4 + Libadwaita application designed for GNOME desktop users to **browse, download, apply, and manage** GTK themes, GNOME Shell themes, Icon themes, Cursor themes, and Wallpapers — with zero terminal hassle or manual file copying.

---

## 📸 Screenshots

| 🏪 Store & Theme Discovery | 📦 Installed Themes & Active Management |
| :---: | :---: |
| ![Store View](screenshots/store.png) | ![Installed View](screenshots/installed.png) |

<p align="center">
  <b>Detailed Theme Preview & Package Selector</b><br>
  <img src="screenshots/details.png" width="90%" alt="Details View">
</p>

---

## 🚀 Installation Guide

Choose your favorite Linux distribution or package format below:

### 1. 🟣 Ubuntu / Debian / Linux Mint / Pop!_OS (`.deb`)
Download and install the native `.deb` package directly:

```bash
# Download latest .deb package
wget https://github.com/manasdotio/motif/releases/download/v1.0.1/motif_1.0.0_all.deb

# Install package
sudo apt install ./motif_1.0.0_all.deb
```
*(Or double-click `motif_1.0.0_all.deb` in your file manager to install via Ubuntu Software).*

---

### 2. 🐧 Universal Standalone AppImage (All Linux Distros)
Runs on **Ubuntu, Fedora, Arch Linux, Debian, openSUSE, Pop!_OS, Linux Mint**:

```bash
# Download AppImage
wget https://github.com/manasdotio/motif/releases/download/v1.0.1/Motif-x86_64.AppImage

# Make executable and run
chmod +x Motif-x86_64.AppImage
./Motif-x86_64.AppImage
```

---

### 3. 📦 Flatpak (Flathub)

```bash
# Install via Flathub
flatpak install flathub io.github.manasdotio.motif

# Run Motif
flatpak run io.github.manasdotio.motif
```

---

### 4. 🏔️ Arch Linux / Manjaro (AUR & PKGBUILD)
Build and install directly using the included `PKGBUILD`:

```bash
# Build & install package
git clone https://github.com/manasdotio/motif.git
cd motif
makepkg -si
```

---

### 5. 🎩 Fedora / RHEL (RPM & Copr)
Build RPM using `motif.spec`:

```bash
# Build RPM package
git clone https://github.com/manasdotio/motif.git
cd motif
rpmbuild -ba motif.spec
```

---

### 6. 🐍 Python Pip (Universal Wheel)

```bash
# Install via pip
pip install https://github.com/manasdotio/motif/releases/download/v1.0.1/motif-1.0.0-py3-none-any.whl

# Run Motif
motif
```

---

## ✨ Feature Highlights

- 🏪 **Store Tab**:
  - Browse GTK, GNOME Shell, Icon, and Cursor themes from `gnome-look.org` (OCS API).
  - Debounced search, sorting by rating, downloads, or date, and infinite scroll pagination.
  - Interactive multi-file package picker & screenshot carousels.
- 🐙 **GitHub & Direct URL Theme Installer**:
  - Paste any GitHub repository URL (e.g. `https://github.com/vinceliuice/Orchis-theme`) or direct `.zip` archive URL.
  - Customization Options Dialog: Color scheme (Dark, Light), accent colors, compact sizes, and Libadwaita app patches.
- ⚙️ **Direct Live GSettings Application**:
  - Instant theme application via `Gio.Settings` (no CLI subprocesses).
  - Built-in Rollback ("Revert Last Change") history.
  - Active theme radio selection and automatic reversion to `Adwaita` before deletion.

---

## 🛠️ Local Development & Testing

```bash
# Clone repository
git clone https://github.com/manasdotio/motif.git
cd motif

# Create virtual environment with system PyGObject bindings
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e .

# Run Unit Test Suite (50 tests passing)
PYTHONPATH=. .venv/bin/pytest

# Launch Motif
PYTHONPATH=. .venv/bin/python3 -m motif.main
```

---

## 📄 License
Motif is licensed under the [GNU General Public License v3.0 or later (GPL-3.0-or-later)](LICENSE).
