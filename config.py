import json
import os

DEFAULT_DATA_DIR = os.path.join(os.path.expanduser("~"), "חוות_דעת_רפואיות")
CONFIG_FILE = "config.json"

# Bootstrap config lives NEXT TO the app (not inside data dir)
# so it can remember the chosen data directory across restarts.
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_BOOTSTRAP_PATH = os.path.join(_APP_DIR, "app_settings.json")


def _load_bootstrap():
    """Load the bootstrap settings (data_dir path)."""
    if os.path.exists(_BOOTSTRAP_PATH):
        try:
            with open(_BOOTSTRAP_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_bootstrap(data):
    """Save bootstrap settings."""
    with open(_BOOTSTRAP_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_data_dir():
    """Return the data directory, creating it if needed."""
    # Priority: 1) env var  2) bootstrap config  3) default
    env_override = os.environ.get("MEDICAL_OPINION_DATA_DIR")
    if env_override:
        data_dir = env_override
    else:
        bootstrap = _load_bootstrap()
        data_dir = bootstrap.get("data_dir", DEFAULT_DATA_DIR)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def set_data_dir(new_path):
    """Change the working data directory.

    Creates the directory if needed and migrates the bootstrap config.
    Returns the resolved path.
    """
    new_path = os.path.abspath(os.path.expanduser(new_path))
    os.makedirs(new_path, exist_ok=True)

    # Ensure subdirectories exist
    os.makedirs(os.path.join(new_path, "תיקים"), exist_ok=True)

    bootstrap = _load_bootstrap()
    bootstrap["data_dir"] = new_path
    _save_bootstrap(bootstrap)

    return new_path


def get_config_path():
    return os.path.join(get_data_dir(), CONFIG_FILE)


DEFAULT_GITHUB_REPO = "tal2420/MedicalOpinion"


def _default_config():
    return {
        "email_address": "",
        "email_password": "",
        "imap_server": "imap.gmail.com",
        "imap_port": 993,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "professor_name": "",
        "professor_title": "פרופסור",
        "professor_specialty": "אורולוגיה",
        "professor_license": "",
        "professor_phone": "",
        "professor_address": "",
        "github_repo": DEFAULT_GITHUB_REPO,
        "collector_url": "",
        "telemetry_enabled": True,
    }


def load_config():
    """Load configuration from JSON file.

    Always merges with defaults so that new fields (like github_repo) are
    populated even when an existing config.json was created before they
    existed. The merged result is also written back to disk so the user
    sees the default values pre-filled in the UI.
    """
    defaults = _default_config()
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                stored = json.load(f)
        except Exception:
            stored = {}

        # Merge: defaults supply missing keys; stored values win otherwise.
        merged = dict(defaults)
        for k, v in stored.items():
            merged[k] = v

        # Backfill empty github_repo with the default (so existing installs
        # automatically get the right repo configured)
        if not merged.get("github_repo"):
            merged["github_repo"] = DEFAULT_GITHUB_REPO

        # Persist the merged config so the new defaults stick
        if merged != stored:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(merged, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        return merged

    return defaults


def save_config(config):
    """Save configuration to JSON file."""
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
