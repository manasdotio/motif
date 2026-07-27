"""
Core logic for importing, downloading, and customizing themes from GitHub repositories or direct archive URLs.
"""
import os
import re
import shutil
import tempfile
import subprocess
import logging
from typing import Callable, Optional, Dict, List

from motif.core.installer import ThemeInstaller, InstallationError
from motif.core.validators import find_extracted_theme_roots, validate_theme_structure, ValidationError
from motif.core.utils import safe_remove_path

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, float], None]

def parse_github_url(url: str) -> Optional[Dict[str, str]]:
    """
    Parses a GitHub URL to extract owner, repo, and constructs archive zip URLs.
    Example inputs:
      - https://github.com/vinceliuice/Orchis-theme
      - https://github.com/vinceliuice/Orchis-theme.git
      - https://github.com/vinceliuice/Orchis-theme/tree/master
    """
    clean_url = url.strip().rstrip("/")
    if clean_url.endswith(".git"):
        clean_url = clean_url[:-4]

    pattern = r"^https?://github\.com/([^/]+)/([^/]+)(?:/(?:tree|blob)/([^/]+))?"
    match = re.match(pattern, clean_url)
    if not match:
        return None

    owner, repo, branch = match.groups()
    default_branch = branch or "main"

    return {
        "owner": owner,
        "repo": repo,
        "branch": default_branch,
        "zip_main": f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip",
        "zip_master": f"https://github.com/{owner}/{repo}/archive/refs/heads/master.zip",
        "raw_git": f"https://github.com/{owner}/{repo}.git",
    }


def parse_install_script_help(help_text: str, script_content: str = "", repo_name: str = "") -> Dict[str, any]:
    """
    Parses help text or script contents from `./install.sh` to extract options for color, accent, size, and libadwaita.
    Includes smart fallback presets for popular theme repositories like Catppuccin, Orchis, Fluent, WhiteSur.
    """
    res: Dict[str, any] = {
        "colors": [],
        "accents": [],
        "styles": [],
        "tweaks": [],
        "has_libadwaita": False
    }

    combined_text = (help_text + "\n" + script_content).lower()
    repo_lower = repo_name.lower()

    if "--libadwaita" in combined_text or "-l" in combined_text or "libadwaita" in repo_lower:
        res["has_libadwaita"] = True

    # 1. Preset matching for known major theme families
    if "catppuccin" in repo_lower or "catppuccin" in combined_text:
        res["colors"] = ["mocha", "macchiato", "frappe", "latte", "black"]
        res["accents"] = ["teal", "blue", "flamingo", "green", "lavender", "maroon", "mauve", "peach", "pink", "red", "rosewater", "sapphire", "sky", "yellow"]
        res["has_libadwaita"] = True
        res["styles"] = ["standard", "compact"]
        res["tweaks"] = ["files-legacy", "macos", "rimless", "black", "radius 14", "opacity 0.75"]
        res["tweaks_hint"] = "--tweaks files-legacy macos radius 14 --shell opacity 0.75 radius 14"
        return res

    if "orchis" in repo_lower:
        res["colors"] = ["default", "dark", "light"]
        res["accents"] = ["default", "purple", "pink", "red", "orange", "yellow", "green", "teal", "blue"]
        res["styles"] = ["standard", "compact"]
        res["has_libadwaita"] = True
        res["tweaks"] = ["macos", "flat", "compact", "dock", "solid"]
        res["tweaks_hint"] = "--tweaks macos flat compact solid"
        return res

    if "whitesur" in repo_lower or "mojave" in repo_lower:
        res["colors"] = ["light", "dark"]
        res["accents"] = ["default", "blue", "purple", "pink", "red", "orange", "yellow", "green", "grey"]
        res["styles"] = ["standard", "compact"]
        res["has_libadwaita"] = True
        res["tweaks"] = ["macos", "nord", "alt", "dark", "flat"]
        res["tweaks_hint"] = "--tweaks macos nord alt"
        return res

    # 2. General Regex Extraction from help text / script
    color_match = re.search(r"(?:-c|--color)[^\n]*?(?:\[|:|\()(.*?)(?:\]|\n|\))", help_text, re.IGNORECASE)
    if color_match:
        items = re.split(r"[|,\s]+", color_match.group(1))
        res["colors"] = [i.strip().lower() for i in items if i.strip() and i.strip().lower() not in ("variants...", "specifies", "color", "variant", "variants")]

    accent_match = re.search(r"(?:-a|--accent)[^\n]*?(?:\[|:|\()(.*?)(?:\]|\n|\))", help_text, re.IGNORECASE)
    if accent_match:
        items = re.split(r"[|,\s]+", accent_match.group(1))
        res["accents"] = [i.strip().lower() for i in items if i.strip() and i.strip().lower() not in ("accents...", "specifies", "accent", "accents")]

    style_match = re.search(r"(?:-s|--size|--style)[^\n]*?(?:\[|:|\()(.*?)(?:\]|\n|\))", help_text, re.IGNORECASE)
    if style_match:
        items = re.split(r"[|,\s]+", style_match.group(1))
        res["styles"] = [i.strip().lower() for i in items if i.strip() and i.strip().lower() not in ("sizes...", "specifies", "size", "sizes")]

    tweak_match = re.search(r"(?:-t|--tweaks|--shell)[^\n]*?(?:\[|:|\()(.*?)(?:\]|\n|\))", help_text, re.IGNORECASE)
    if tweak_match:
        items = re.split(r"[|,\s]+", tweak_match.group(1))
        res["tweaks"] = [i.strip().lower() for i in items if i.strip() and i.strip().lower() not in ("tweaks...", "specifies", "tweak", "tweaks")]
        res["tweaks_hint"] = f"--tweaks {' '.join(res['tweaks'][:4])}"

    return res


import shlex

class GitHubInstaller:
    """
    Manages downloading, customizing, and installing themes from GitHub or direct URLs.
    """

    def __init__(self, theme_installer: Optional[ThemeInstaller] = None):
        self.installer = theme_installer or ThemeInstaller()

    def inspect_repository_options(self, url: str) -> Dict[str, any]:
        """
        Inspects repository install.sh script help text to dynamically discover customization choices.
        """
        gh_info = parse_github_url(url)
        if not gh_info:
            return {"has_script": False, "colors": [], "accents": [], "styles": [], "has_libadwaita": False}

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = os.path.join(temp_dir, "repo")
            downloaded = False
            if shutil.which("git"):
                try:
                    res = subprocess.run(
                        ["git", "clone", "--depth", "1", gh_info["raw_git"], repo_dir],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=30,
                        text=True
                    )
                    if res.returncode == 0 and os.path.exists(repo_dir):
                        downloaded = True
                except Exception as e:
                    logger.warning(f"git clone inspection failed: {e}")

            if not downloaded:
                # Fast preset check if git clone fails
                opts = parse_install_script_help("", "", repo_info_name := gh_info["repo"])
                if opts["colors"] or opts["accents"]:
                    opts["has_script"] = True
                    opts["repo_name"] = repo_info_name
                    return opts
                return {"has_script": False, "colors": [], "accents": [], "styles": [], "has_libadwaita": False}

            install_script = os.path.join(repo_dir, "install.sh")
            if not os.path.exists(install_script):
                for root, dirs, files in os.walk(repo_dir):
                    if "install.sh" in files:
                        install_script = os.path.join(root, "install.sh")
                        break

            if os.path.exists(install_script):
                os.chmod(install_script, 0o755)
                help_out = ""
                script_content = ""
                try:
                    with open(install_script, "r", encoding="utf-8", errors="ignore") as f:
                        script_content = f.read()
                except Exception:
                    pass

                try:
                    proc = subprocess.run(
                        [install_script, "--help"],
                        cwd=os.path.dirname(install_script),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=10,
                        text=True
                    )
                    help_out = proc.stdout
                except Exception:
                    pass

                opts = parse_install_script_help(help_out, script_content, gh_info["repo"])
                opts["has_script"] = True
                opts["repo_name"] = gh_info["repo"]
                return opts

        return {"has_script": False, "colors": [], "accents": [], "styles": [], "has_libadwaita": False}

    def build_install_script_flags(
        self,
        color: str = "default",
        accent: str = "default",
        style: str = "default",
        libadwaita: bool = False,
        custom_flags: str = "",
        target_dir: Optional[str] = None
    ) -> List[str]:
        """
        Builds common command-line arguments for `./install.sh` scripts.
        """
        args = []

        if target_dir:
            args.extend(["-d", target_dir])

        if color and color != "default":
            args.extend(["-c", color])

        if accent and accent != "default":
            args.extend(["-a", accent])

        if style and style != "default":
            if style == "compact":
                args.append("--compact")
            else:
                args.extend(["-s", style])

        if libadwaita:
            args.append("-l")

        if custom_flags and custom_flags.strip():
            try:
                extra = shlex.split(custom_flags.strip())
                args.extend(extra)
            except Exception as e:
                logger.warning(f"Error parsing custom_flags: {e}")

        return args

    def install(
        self,
        url: str,
        type_key: str,
        custom_name: str = "",
        color: str = "default",
        accent: str = "default",
        style: str = "default",
        libadwaita: bool = False,
        custom_flags: str = "",
        progress_cb: Optional[ProgressCallback] = None
    ) -> str:
        """
        End-to-end installation flow for GitHub repositories or direct archives.
        Supports running `./install.sh` scripts with custom flags if present.
        """
        if progress_cb:
            progress_cb("Analyzing URL...", 0.05)

        gh_info = parse_github_url(url)

        # 1. Direct Archive URL flow (if not a GitHub repository URL)
        if not gh_info:
            theme_name = custom_name.strip() or "Imported_Theme"
            return self.installer.install_theme_from_url(
                url=url,
                theme_name=theme_name,
                type_key=type_key,
                progress_cb=progress_cb
            )

        # 2. GitHub Repository Flow
        theme_name = custom_name.strip() or gh_info["repo"]
        target_base_dir = os.path.dirname(self.installer.get_target_directory(type_key, "dummy"))

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = os.path.join(temp_dir, "repo")

            # Download repository (via git clone if available or zip archive download)
            if progress_cb:
                progress_cb("Downloading GitHub repository...", 0.15)

            downloaded = False
            if shutil.which("git"):
                try:
                    res = subprocess.run(
                        ["git", "clone", "--depth", "1", gh_info["raw_git"], repo_dir],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=60,
                        text=True
                    )
                    if res.returncode == 0 and os.path.exists(repo_dir):
                        downloaded = True
                except Exception as e:
                    logger.warning(f"git clone failed: {e}, falling back to zip download")

            if not downloaded:
                # Try main.zip first, then master.zip
                zip_path = os.path.join(temp_dir, "repo.zip")
                try:
                    self.installer.download_file(gh_info["zip_main"], zip_path)
                except Exception:
                    self.installer.download_file(gh_info["zip_master"], zip_path)

                extract_dir = os.path.join(temp_dir, "zip_extract")
                os.makedirs(extract_dir, exist_ok=True)
                self.installer.extract_archive(zip_path, extract_dir, "zip")
                
                # Find inner directory
                if os.path.exists(extract_dir):
                    subdirs = [os.path.join(extract_dir, d) for d in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, d))]
                    if subdirs:
                        repo_dir = subdirs[0]
                    else:
                        repo_dir = extract_dir

            if progress_cb:
                progress_cb("Inspecting repository structure...", 0.50)

            # Check for install.sh script
            install_script = os.path.join(repo_dir, "install.sh")
            if not os.path.exists(install_script):
                # Search one level deep
                for root, dirs, files in os.walk(repo_dir):
                    if "install.sh" in files:
                        install_script = os.path.join(root, "install.sh")
                        repo_dir = root
                        break

            if os.path.exists(install_script):
                if progress_cb:
                    progress_cb("Running theme installer script with custom options...", 0.65)

                # Make executable
                os.chmod(install_script, 0o755)

                flags = self.build_install_script_flags(
                    color=color,
                    accent=accent,
                    style=style,
                    libadwaita=libadwaita,
                    custom_flags=custom_flags,
                    target_dir=target_base_dir
                )

                cmd = ["./install.sh"] + flags
                logger.info(f"Executing installer in {repo_dir}: {' '.join(cmd)}")

                try:
                    proc = subprocess.run(
                        cmd,
                        cwd=repo_dir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=120,
                        text=True
                    )
                    logger.info(f"Installer output:\n{proc.stdout}")
                except Exception as e:
                    raise InstallationError(f"Error running install.sh script: {e}")

                if progress_cb:
                    progress_cb("Verifying installation...", 0.90)

                target_path = self.installer.get_target_directory(type_key, theme_name)
                if progress_cb:
                    progress_cb("Installation completed!", 1.0)
                return target_path
            else:
                # No install.sh present -> manual structure validation & copying
                if progress_cb:
                    progress_cb("Extracting theme files...", 0.70)

                roots = find_extracted_theme_roots(repo_dir, type_key)
                if not roots:
                    raise InstallationError("No valid theme files or install.sh script found in repository.")

                installed_paths = []
                for root in roots:
                    folder_name = os.path.basename(root) if len(roots) > 1 else theme_name
                    target_path = self.installer.get_target_directory(type_key, folder_name)

                    if os.path.exists(target_path):
                        safe_remove_path(target_path)

                    shutil.copytree(root, target_path)
                    installed_paths.append(target_path)

                if progress_cb:
                    progress_cb("Installation completed!", 1.0)

                return installed_paths[0]
