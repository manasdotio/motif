"""
Unit tests for theme installer.
"""
import os
import tarfile
import tempfile
import pytest

from motif.core.installer import ThemeInstaller, InstallationError

def test_installer_target_directory():
    with tempfile.TemporaryDirectory() as tmp_base:
        installer = ThemeInstaller(base_install_dir=tmp_base)

        target = installer.get_target_directory("gtk", "SampleTheme")
        assert target == os.path.join(tmp_base, "SampleTheme")

def test_extract_and_install_tar():
    with tempfile.TemporaryDirectory() as tmp_install_dir:
        installer = ThemeInstaller(base_install_dir=tmp_install_dir)

        # Create a mock theme tar archive
        with tempfile.TemporaryDirectory() as src_dir:
            theme_folder = os.path.join(src_dir, "MyGtkTheme")
            os.makedirs(os.path.join(theme_folder, "gtk-3.0"))
            with open(os.path.join(theme_folder, "gtk-3.0", "gtk.css"), "w") as f:
                f.write("body {}")
            with open(os.path.join(theme_folder, "index.theme"), "w") as f:
                f.write("[Desktop Entry]\nName=MyGtkTheme")

            tar_path = os.path.join(src_dir, "theme.tar.gz")
            with tarfile.open(tar_path, "w:gz") as tf:
                tf.add(theme_folder, arcname="MyGtkTheme")

            # Extract archive
            with tempfile.TemporaryDirectory() as extract_dir:
                installer.extract_archive(tar_path, extract_dir, "tar")

                from motif.core.validators import find_extracted_theme_root, validate_theme_structure
                theme_root = find_extracted_theme_root(extract_dir, "gtk")
                validate_theme_structure(theme_root, "gtk")

                assert os.path.exists(os.path.join(theme_root, "gtk-3.0", "gtk.css"))
