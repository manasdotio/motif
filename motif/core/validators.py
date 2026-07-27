"""
Validation rules for extracted themes and archives.
"""
import os
import tarfile
import zipfile
from typing import List, Optional

class ValidationError(Exception):
    """Exception raised when a theme archive or directory structure is invalid."""
    pass

def validate_archive_file(file_path: str) -> str:
    """
    Validates that a file is a supported valid tar/zip archive.
    Returns 'tar' or 'zip'. Raises ValidationError if corrupt or unsupported.
    """
    if not os.path.isfile(file_path):
        raise ValidationError(f"File not found: {file_path}")

    # Check zip
    if zipfile.is_zipfile(file_path):
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                bad_file = zf.testzip()
                if bad_file:
                    raise ValidationError(f"Corrupt zip archive, bad file: {bad_file}")
            return "zip"
        except Exception as e:
            raise ValidationError(f"Invalid zip archive: {e}")

    # Check tar
    if tarfile.is_tarfile(file_path):
        try:
            with tarfile.open(file_path, 'r:*') as tf:
                # Test reading members list
                tf.getmembers()
            return "tar"
        except Exception as e:
            raise ValidationError(f"Invalid tar archive: {e}")

    raise ValidationError(f"File is not a valid zip or tar archive: {os.path.basename(file_path)}")

def is_theme_directory(path: str, type_key: str) -> bool:
    """Checks if a directory path contains valid theme files/folders for type_key."""
    if not os.path.isdir(path):
        return False
    try:
        entries = set(os.listdir(path))
    except Exception:
        return False

    if type_key == "cursor":
        return "cursors" in entries or "index.theme" in entries
    elif type_key == "icon":
        return "index.theme" in entries or any(e in entries for e in ("16x16", "22x22", "32x32", "scalable", "apps"))
    elif type_key in ("gtk", "shell"):
        return any(e in entries for e in ("gtk-3.0", "gtk-4.0", "gnome-shell", "gnome-shell.css", "index.theme", "gtk-2.0"))
    elif type_key == "wallpaper":
        image_exts = {".png", ".jpg", ".jpeg", ".webp", ".jxl", ".svg"}
        return any(os.path.splitext(e)[1].lower() in image_exts for e in entries)
    return False

def find_extracted_theme_roots(extracted_dir: str, type_key: str) -> List[str]:
    """
    Scans extracted_dir and returns all valid theme root directories found.
    Handles extra top-level wrapper folders, extra files (README, LICENSE), or nested theme variants.
    """
    if is_theme_directory(extracted_dir, type_key):
        return [extracted_dir]

    found_roots = []
    # Search up to 3 levels deep
    for root, dirs, files in os.walk(extracted_dir):
        rel_path = os.path.relpath(root, extracted_dir)
        depth = 0 if rel_path == "." else len(rel_path.split(os.sep))
        if depth > 3:
            continue

        if root != extracted_dir and is_theme_directory(root, type_key):
            # Ensure root is not a child of an already identified root
            if not any(root.startswith(parent + os.sep) for parent in found_roots):
                found_roots.append(root)

    if found_roots:
        return found_roots

    # Fallback to single top-level directory if present
    entries = [e for e in os.listdir(extracted_dir) if not e.startswith(".") and e not in ("__MACOSX",)]
    if len(entries) == 1:
        single_path = os.path.join(extracted_dir, entries[0])
        if os.path.isdir(single_path):
            return [single_path]

    return [extracted_dir]

def find_extracted_theme_root(extracted_dir: str, type_key: str) -> str:
    """
    Returns the primary theme root directory found in extracted_dir.
    """
    roots = find_extracted_theme_roots(extracted_dir, type_key)
    return roots[0]

def validate_theme_structure(theme_dir: str, type_key: str) -> None:
    """
    Validates theme directory contents according to theme type.
    Raises ValidationError if required files/directories are missing.
    """
    if not os.path.isdir(theme_dir):
        raise ValidationError(f"Path is not a directory: {theme_dir}")

    files_and_dirs = set(os.listdir(theme_dir))

    if type_key == "cursor":
        has_cursors_dir = False
        has_index_theme = False

        # Look in theme_dir and any immediate single top-level child
        if "cursors" in files_and_dirs and os.path.isdir(os.path.join(theme_dir, "cursors")):
            has_cursors_dir = True
        if "index.theme" in files_and_dirs:
            has_index_theme = True

        missing = []
        if not has_cursors_dir:
            missing.append("'cursors/' directory")
        if not has_index_theme:
            missing.append("'index.theme' file")

        if missing:
            err_msg = (
                f"Invalid Cursor Theme in '{os.path.basename(theme_dir)}': "
                f"Missing {', '.join(missing)}. "
                f"Cursor themes require a 'cursors/' folder and an 'index.theme' file."
            )
            raise ValidationError(err_msg)

    elif type_key == "icon":
        if "index.theme" not in files_and_dirs:
            raise ValidationError(
                f"Invalid Icon Theme in '{os.path.basename(theme_dir)}': "
                "Missing 'index.theme' file."
            )

    elif type_key == "gtk":
        # Check for gtk-3.0, gtk-4.0, or index.theme
        has_gtk3 = "gtk-3.0" in files_and_dirs
        has_gtk4 = "gtk-4.0" in files_and_dirs
        has_index = "index.theme" in files_and_dirs
        has_css = any(f.endswith(".css") for f in files_and_dirs)

        if not (has_gtk3 or has_gtk4 or has_index or has_css):
            raise ValidationError(
                f"Invalid GTK Theme in '{os.path.basename(theme_dir)}': "
                "Must contain 'gtk-3.0/', 'gtk-4.0/', or 'index.theme'."
            )

    elif type_key == "shell":
        # Check for gnome-shell/ or gnome-shell.css or index.theme
        has_shell_dir = "gnome-shell" in files_and_dirs
        has_shell_css = "gnome-shell.css" in files_and_dirs
        has_index = "index.theme" in files_and_dirs

        if not (has_shell_dir or has_shell_css or has_index):
            raise ValidationError(
                f"Invalid Shell Theme in '{os.path.basename(theme_dir)}': "
                "Must contain 'gnome-shell/' directory, 'gnome-shell.css', or 'index.theme'."
            )

    elif type_key == "wallpaper":
        # Check for image file or directory containing images
        image_exts = {".png", ".jpg", ".jpeg", ".webp", ".jxl", ".svg"}
        found_image = False
        for root, _, files in os.walk(theme_dir):
            if any(os.path.splitext(f)[1].lower() in image_exts for f in files):
                found_image = True
                break
        if not found_image:
            raise ValidationError(
                f"Invalid Wallpaper package in '{os.path.basename(theme_dir)}': "
                "No image files (.png, .jpg, .svg, etc.) found."
            )
