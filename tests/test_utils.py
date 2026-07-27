import os
import stat
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from motif.core.utils import safe_remove_path


class TestUtils(unittest.TestCase):
    def test_safe_remove_path_normal_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        self.assertTrue(os.path.exists(tmp_path))
        safe_remove_path(tmp_path)
        self.assertFalse(os.path.exists(tmp_path))

    def test_safe_remove_path_readonly_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        os.chmod(tmp_path, stat.S_IRUSR)
        safe_remove_path(tmp_path)
        self.assertFalse(os.path.exists(tmp_path))

    def test_safe_remove_path_readonly_dir(self):
        tmp_dir = tempfile.mkdtemp()
        sub_file = os.path.join(tmp_dir, "file.txt")
        with open(sub_file, "w") as f:
            f.write("test")
        os.chmod(sub_file, stat.S_IRUSR)
        os.chmod(tmp_dir, stat.S_IRUSR | stat.S_IXUSR)

        safe_remove_path(tmp_dir)
        self.assertFalse(os.path.exists(tmp_dir))

    @patch("subprocess.run")
    def test_safe_remove_path_permission_error_escalates_to_pkexec(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        with patch("os.path.lexists", return_value=True), \
             patch("os.path.isdir", return_value=True), \
             patch("shutil.rmtree", side_effect=PermissionError("Permission denied")):
            safe_remove_path("/usr/share/themes/SystemTheme")
            mock_run.assert_called_once_with(
                ["pkexec", "rm", "-rf", "/usr/share/themes/SystemTheme"],
                capture_output=True,
                text=True
            )

    @patch("subprocess.run")
    def test_safe_remove_path_pkexec_failure_raises_permission_error(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="Authentication failed")
        with patch("os.path.lexists", return_value=True), \
             patch("os.path.isdir", return_value=True), \
             patch("shutil.rmtree", side_effect=PermissionError("Permission denied")):
            with self.assertRaises(PermissionError) as ctx:
                safe_remove_path("/usr/share/themes/SystemTheme")
            self.assertIn("Authentication failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
