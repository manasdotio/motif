"""
Unit tests for theme validators.
"""
import os
import tarfile
import zipfile
import tempfile
import pytest

from motif.core.validators import (
    ValidationError,
    validate_archive_file,
    find_extracted_theme_root,
    validate_theme_structure,
)

def test_validate_archive_file_zip():
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test.txt", "hello world")

        assert validate_archive_file(zip_path) == "zip"

def test_validate_archive_file_tar():
    with tempfile.TemporaryDirectory() as tmpdir:
        tar_path = os.path.join(tmpdir, "test.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tf:
            fpath = os.path.join(tmpdir, "test.txt")
            with open(fpath, "w") as f:
                f.write("hello")
            tf.add(fpath, arcname="test.txt")

        assert validate_archive_file(tar_path) == "tar"

def test_validate_archive_invalid():
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_path = os.path.join(tmpdir, "bad.tar.gz")
        with open(bad_path, "w") as f:
            f.write("this is not a tar archive")

        with pytest.raises(ValidationError):
            validate_archive_file(bad_path)

def test_find_extracted_theme_root_flattening():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Extra nested folder MyTheme-v1/
        wrapper = os.path.join(tmpdir, "MyTheme-v1")
        os.makedirs(wrapper)
        with open(os.path.join(wrapper, "index.theme"), "w") as f:
            f.write("[Icon Theme]\nName=MyTheme")

        root = find_extracted_theme_root(tmpdir, "icon")
        assert root == wrapper

def test_validate_cursor_theme_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "cursors"))
        with open(os.path.join(tmpdir, "index.theme"), "w") as f:
            f.write("[Icon Theme]\nName=CursorTest")

        # Should not raise
        validate_theme_structure(tmpdir, "cursor")

def test_validate_cursor_theme_missing_cursors():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "index.theme"), "w") as f:
            f.write("[Icon Theme]\nName=CursorTest")

        with pytest.raises(ValidationError) as exc:
            validate_theme_structure(tmpdir, "cursor")
        assert "cursors" in str(exc.value).lower()

        validate_theme_structure(tmpdir, "gtk")

def test_find_extracted_theme_roots_with_extra_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Theme subfolder alongside README and LICENSE files
        theme_dir = os.path.join(tmpdir, "WhiteSur-Dark")
        os.makedirs(os.path.join(theme_dir, "gtk-3.0"))
        with open(os.path.join(tmpdir, "README.md"), "w") as f:
            f.write("# Instructions")
        with open(os.path.join(tmpdir, "LICENSE"), "w") as f:
            f.write("GPL-3.0")

        root = find_extracted_theme_root(tmpdir, "gtk")
        assert root == theme_dir

