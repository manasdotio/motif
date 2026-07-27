"""
Theme installer engine: download -> validate -> extract -> flatten -> place in target directory.
"""
import os
import shutil
import tempfile
import tarfile
import zipfile
import logging
from typing import Callable, Optional
import httpx

from motif.core.validators import (
    ValidationError,
    validate_archive_file,
    find_extracted_theme_root,
    find_extracted_theme_roots,
    validate_theme_structure,
)
from motif.core.utils import safe_remove_path

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, float], None]

class InstallationError(Exception):
    """Exception raised during theme installation."""
    pass

class ThemeInstaller:
    def __init__(self, base_install_dir: Optional[str] = None):
        self.home_dir = os.path.expanduser("~")
        self.base_install_dir = base_install_dir

    def get_target_directory(self, type_key: str, theme_name: str) -> str:
        """
        Determines target installation directory based on category and theme name.
        """
        if self.base_install_dir:
            base = self.base_install_dir
        elif type_key in ("gtk", "shell"):
            base = os.path.join(self.home_dir, ".local", "share", "themes")
        elif type_key in ("icon", "cursor"):
            base = os.path.join(self.home_dir, ".local", "share", "icons")
        elif type_key == "wallpaper":
            base = os.path.join(self.home_dir, ".local", "share", "backgrounds")
        else:
            base = os.path.join(self.home_dir, ".local", "share", "themes")

        os.makedirs(base, exist_ok=True)
        return os.path.join(base, theme_name)

    def download_file(
        self,
        url: str,
        dest_path: str,
        progress_cb: Optional[ProgressCallback] = None
    ) -> None:
        """
        Downloads a file from URL to dest_path with progress updates.
        """
        try:
            with httpx.Client(follow_redirects=True, timeout=30.0) as client:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    total_bytes = int(response.headers.get("content-length", 0))
                    downloaded = 0

                    with open(dest_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=16384):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_cb and total_bytes > 0:
                                    pct = min(1.0, downloaded / total_bytes) * 0.7  # Download is 70% of total
                                    progress_cb(f"Downloading... ({int(pct * 100)}%)", pct)
                                elif progress_cb:
                                    progress_cb("Downloading...", 0.35)
        except Exception as e:
            raise InstallationError(f"Network error downloading file: {e}")

    def extract_archive(self, archive_path: str, extract_to: str, archive_type: str) -> None:
        """Extracts zip or tar archive to destination directory."""
        try:
            if archive_type == "zip":
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    zf.extractall(extract_to)
            elif archive_type == "tar":
                with tarfile.open(archive_path, 'r:*') as tf:
                    # Filter members to avoid path traversal vulnerability (CVE-2007-4559)
                    def is_within_directory(directory, target):
                        abs_directory = os.path.abspath(directory)
                        abs_target = os.path.abspath(target)
                        prefix = os.path.commonprefix([abs_directory, abs_target])
                        return prefix == abs_directory

                    def safe_extract(tar, path=".", members=None, numeric_owner=False):
                        for member in tar.getmembers():
                            member_path = os.path.join(path, member.name)
                            if not is_within_directory(path, member_path):
                                raise InstallationError(f"Attempted Path Traversal in Tar File: {member.name}")
                        tar.extractall(path, members, numeric_owner=numeric_owner)

                    safe_extract(tf, extract_to)
        except Exception as e:
            raise InstallationError(f"Extraction failed: {e}")

    def install_theme_from_url(
        self,
        url: str,
        theme_name: str,
        type_key: str,
        progress_cb: Optional[ProgressCallback] = None
    ) -> str:
        """
        Complete end-to-end installation flow:
        Download -> Validate Archive -> Extract -> Detect Flattening -> Validate Structure -> Move to Target.
        Returns installed path.
        """
        if progress_cb:
            progress_cb("Preparing download...", 0.05)

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_filename = "download_archive"
            archive_path = os.path.join(temp_dir, archive_filename)

            # 1. Download
            self.download_file(url, archive_path, progress_cb)

            # 2. Validate archive format
            if progress_cb:
                progress_cb("Validating archive format...", 0.75)
            try:
                archive_type = validate_archive_file(archive_path)
            except ValidationError as ve:
                raise InstallationError(f"Archive validation failed: {ve}")

            # 3. Extract
            if progress_cb:
                progress_cb("Extracting theme archive...", 0.80)
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            self.extract_archive(archive_path, extract_dir, archive_type)

            # 4. Find true theme root(s) (handle extra top-level folder wrapping and multi-variant archives)
            theme_roots = find_extracted_theme_roots(extract_dir, type_key)

            if progress_cb:
                progress_cb("Validating theme structure...", 0.88)

            installed_paths = []
            for theme_root in theme_roots:
                # Use subfolder name if multiple variant themes exist in archive
                if len(theme_roots) > 1:
                    folder_name = os.path.basename(theme_root)
                else:
                    folder_name = theme_name.strip() or os.path.basename(theme_root)

                # 5. Validate theme structure according to category
                try:
                    validate_theme_structure(theme_root, type_key)
                except ValidationError as ve:
                    raise InstallationError(str(ve))

                # 6. Target path determination
                target_path = self.get_target_directory(type_key, folder_name)

                if progress_cb:
                    progress_cb(f"Installing to {target_path}...", 0.95)

                # 7. Move/Copy to target
                try:
                    if os.path.exists(target_path):
                        safe_remove_path(target_path)

                    shutil.copytree(theme_root, target_path)
                    installed_paths.append(target_path)
                except PermissionError as pe:
                    raise InstallationError(f"Permission denied installing theme to {target_path}: {pe}")
                except Exception as e:
                    raise InstallationError(f"Failed to place theme files in {target_path}: {e}")

            if progress_cb:
                progress_cb("Installation complete!", 1.0)

            return installed_paths[0]
