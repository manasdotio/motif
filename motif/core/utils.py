"""
Utility functions for file management and execution.
"""
import os
import shutil
import stat
import subprocess
import logging

logger = logging.getLogger(__name__)


def _handle_readonly(func, path, exc_info):
    """Error handler for shutil.rmtree to handle read-only files and directories."""
    try:
        parent = os.path.dirname(path)
        if parent and os.path.exists(parent):
            try:
                os.chmod(parent, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
            except Exception:
                pass
        os.chmod(path, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
        func(path)
    except Exception:
        pass


def safe_remove_path(path: str) -> None:
    """
    Safely removes a file, directory, or symlink at `path`.
    Handles read-only files/directories by modifying permissions.
    If standard deletion fails with PermissionError (e.g. system directory or root-owned),
    attempts privilege escalation via pkexec.
    """
    if not os.path.lexists(path):
        return

    try:
        if os.path.islink(path) or os.path.isfile(path):
            try:
                os.remove(path)
            except PermissionError:
                os.chmod(path, stat.S_IWUSR | stat.S_IRUSR)
                os.remove(path)
        elif os.path.isdir(path):
            # Try shutil.rmtree with onexc (Python 3.12+) or onerror fallback
            try:
                shutil.rmtree(path, onexc=lambda func, p, e: _handle_readonly(func, p, None))
            except TypeError:
                shutil.rmtree(path, onerror=_handle_readonly)
        else:
            os.remove(path)
    except PermissionError:
        # Escalation fallback via pkexec rm -rf for system directories / root-owned paths
        logger.info(f"Standard removal failed with PermissionError for {path}. Attempting pkexec rm -rf...")
        result = subprocess.run(["pkexec", "rm", "-rf", path], capture_output=True, text=True)
        if result.returncode != 0:
            err_details = result.stderr.strip() or f"pkexec exited with code {result.returncode}"
            raise PermissionError(f"Permission denied deleting {path}: {err_details}")
