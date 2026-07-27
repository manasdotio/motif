"""
Unit tests for GitHubInstaller and GitHub URL parsing module.
"""
import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from motif.core.github_installer import (
    parse_github_url,
    GitHubInstaller,
)
from motif.core.installer import ThemeInstaller

def test_parse_github_url():
    # Standard repository URL
    res = parse_github_url("https://github.com/vinceliuice/Orchis-theme")
    assert res is not None
    assert res["owner"] == "vinceliuice"
    assert res["repo"] == "Orchis-theme"
    assert res["branch"] == "main"
    assert "refs/heads/main.zip" in res["zip_main"]

    # .git URL
    res_git = parse_github_url("https://github.com/catppuccin/gtk.git")
    assert res_git is not None
    assert res_git["repo"] == "gtk"

    # Branch tree URL
    res_tree = parse_github_url("https://github.com/catppuccin/gtk/tree/master")
    assert res_tree is not None
    assert res_tree["branch"] == "master"

    # Non-github URL
    assert parse_github_url("https://example.com/theme.tar.gz") is None


def test_build_install_script_flags():
    installer = GitHubInstaller()

    flags = installer.build_install_script_flags(
        color="dark",
        accent="purple",
        style="compact",
        libadwaita=True,
        custom_flags="--tweaks radius 14 macos --shell opacity 0.75",
        target_dir="/tmp/themes"
    )

    assert "-d" in flags
    assert "/tmp/themes" in flags
    assert "-c" in flags
    assert "dark" in flags
    assert "-a" in flags
    assert "purple" in flags
    assert "--compact" in flags
    assert "-l" in flags
    assert "--tweaks" in flags
    assert "radius" in flags
    assert "14" in flags
    assert "macos" in flags
    assert "--shell" in flags
    assert "opacity" in flags
    assert "0.75" in flags


def test_install_direct_url(tmp_path):
    mock_theme_installer = MagicMock(spec=ThemeInstaller)
    mock_theme_installer.install_theme_from_url.return_value = str(tmp_path / "DirectTheme")

    gh_installer = GitHubInstaller(theme_installer=mock_theme_installer)

    res = gh_installer.install(
        url="https://example.com/mytheme.tar.xz",
        type_key="gtk",
        custom_name="DirectTheme"
    )

    assert res == str(tmp_path / "DirectTheme")
    mock_theme_installer.install_theme_from_url.assert_called_once()


def test_install_github_repo_with_script(tmp_path):
    target_dir = tmp_path / "target_themes"
    target_dir.mkdir()

    mock_theme_installer = MagicMock(spec=ThemeInstaller)
    mock_theme_installer.get_target_directory.return_value = str(target_dir / "TestRepo")

    gh_installer = GitHubInstaller(theme_installer=mock_theme_installer)

    with patch("shutil.which", return_value="/usr/bin/git"), \
         patch("subprocess.run") as mock_run:

        # Mock git clone and install.sh execution
        def side_effect(cmd, *args, **kwargs):
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_res.stdout = "Installed successfully"
            # If command is git clone, create fake repo directory with install.sh
            if "git" in cmd[0]:
                repo_path = cmd[-1]
                os.makedirs(repo_path, exist_ok=True)
                with open(os.path.join(repo_path, "install.sh"), "w") as f:
                    f.write("#!/bin/bash\necho ok")
            return mock_res

        mock_run.side_effect = side_effect

        res = gh_installer.install(
            url="https://github.com/user/TestRepo",
            type_key="gtk",
            color="dark",
            accent="blue",
            style="compact",
            libadwaita=True
        )

        assert res == str(target_dir / "TestRepo")
        assert mock_run.call_count >= 2


def test_parse_install_script_help():
    from motif.core.github_installer import parse_install_script_help

    sample_help = """
    Usage: ./install.sh [OPTION]...
    -c, --color   VARIANTS... [mocha|macchiato|frappe|latte]
    -a, --accent  ACCENTS... [blue|teal|mauve|pink]
    -s, --size    SIZES... [standard|compact]
    -l, --libadwaita           Patch GTK4/Libadwaita
    """

    res = parse_install_script_help(sample_help)
    assert res["has_libadwaita"] is True
    assert "mocha" in res["colors"]
    assert "macchiato" in res["colors"]
    assert "teal" in res["accents"]
    assert "compact" in res["styles"]

