"""
Manual update mechanism via GitHub Releases.
Uses only stdlib - no extra dependencies.
"""

import json
import os
import shutil
import tempfile
import zipfile
from urllib.request import urlopen, Request
from urllib.error import URLError

APP_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(APP_DIR, "VERSION")

# Files/folders that should NEVER be overwritten by an update
PROTECTED = {
    "config.json",
    "app_settings.json",
    ".git",
    "__pycache__",
}


def get_current_version():
    """Read the current version from the VERSION file."""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    return "0.0.0"


def _parse_version(v):
    """Parse a semver string like '1.2.3' into a comparable tuple."""
    v = v.lstrip("vV")
    parts = v.split(".")
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(0)
    while len(result) < 3:
        result.append(0)
    return tuple(result)


def _github_api(repo, endpoint=""):
    """Call the GitHub API. Returns parsed JSON."""
    url = f"https://api.github.com/repos/{repo}{endpoint}"
    req = Request(url, headers={
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "MedicalOpinion-Updater",
    })
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_for_update(github_repo):
    """Check if a newer version is available on GitHub.

    Args:
        github_repo: "owner/repo" string (e.g. "user/MedicalOpinion")

    Returns:
        dict with: available, current_version, latest_version,
                   release_notes, download_url, published_at
    """
    current = get_current_version()
    result = {
        "available": False,
        "current_version": current,
        "latest_version": current,
        "release_notes": "",
        "download_url": "",
        "published_at": "",
    }

    if not github_repo or "/" not in github_repo:
        result["error"] = "GitHub repo not configured (format: owner/repo)"
        return result

    try:
        release = _github_api(github_repo, "/releases/latest")
    except URLError as e:
        result["error"] = f"Could not reach GitHub: {e}"
        return result
    except Exception as e:
        result["error"] = str(e)
        return result

    latest_tag = release.get("tag_name", "0.0.0")
    latest_version = latest_tag.lstrip("vV")

    result["latest_version"] = latest_version
    result["release_notes"] = release.get("body", "")
    result["published_at"] = release.get("published_at", "")

    if _parse_version(latest_version) > _parse_version(current):
        result["available"] = True
        # Always use the source code zipball for in-place updates.
        # The Portable/Setup assets are compiled binaries for fresh installs,
        # not suitable for overwriting a source-code installation.
        result["download_url"] = release.get("zipball_url", "")

    return result


def download_and_apply(download_url):
    """Download a release zip and apply it over the current app directory.

    Skips protected files (config, settings, data).
    Creates a backup of current files before overwriting.

    Args:
        download_url: URL to the release zip file

    Returns:
        dict with: success, message, backup_path
    """
    if not download_url:
        return {"success": False, "message": "No download URL provided"}

    tmp_dir = tempfile.mkdtemp(prefix="medical_opinion_update_")
    zip_path = os.path.join(tmp_dir, "update.zip")
    extract_dir = os.path.join(tmp_dir, "extracted")
    backup_dir = os.path.join(tmp_dir, "backup")

    try:
        # Step 1: Download
        req = Request(download_url, headers={"User-Agent": "MedicalOpinion-Updater"})
        with urlopen(req, timeout=120) as resp:
            with open(zip_path, "wb") as f:
                f.write(resp.read())

        # Step 2: Extract
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # GitHub zipball extracts to a subfolder like "owner-repo-hash/"
        # Find the actual content root
        contents = os.listdir(extract_dir)
        if len(contents) == 1 and os.path.isdir(os.path.join(extract_dir, contents[0])):
            source_dir = os.path.join(extract_dir, contents[0])
        else:
            source_dir = extract_dir

        # Step 3: Backup current app files
        os.makedirs(backup_dir, exist_ok=True)
        for item in os.listdir(APP_DIR):
            if item in PROTECTED or item.startswith("."):
                continue
            src = os.path.join(APP_DIR, item)
            dst = os.path.join(backup_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        # Step 4: Copy new files over (skip protected)
        updated_files = []
        for item in os.listdir(source_dir):
            if item in PROTECTED or item.startswith("."):
                continue
            src = os.path.join(source_dir, item)
            dst = os.path.join(APP_DIR, item)
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            updated_files.append(item)

        # Clean up zip (keep backup)
        os.remove(zip_path)
        shutil.rmtree(extract_dir)

        return {
            "success": True,
            "message": f"Updated {len(updated_files)} files. Restart the app to apply.",
            "backup_path": backup_dir,
            "updated_files": updated_files,
        }

    except Exception as e:
        return {"success": False, "message": f"Update failed: {e}"}
