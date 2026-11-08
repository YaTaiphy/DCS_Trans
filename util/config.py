"""
Persistent Configuration

Saves and loads user preferences (API key, path, options) as defaults
so users don't have to re-enter them every session.

Stored at ./cache/config.json (gitignored — contains API key).
"""

import os
import sys
import json


# ---------------------------------------------------------------------------
# Path resolution — works in dev AND bundled exe (Nuitka/PyInstaller)
# ---------------------------------------------------------------------------
# When a compiled exe is double-clicked from Explorer, CWD is unreliable
# (it can be system32, desktop, etc.). We resolve cache/config paths
# relative to the exe's location when running as a bundled app, and
# relative to CWD when running from source (python <script>.py).
# ---------------------------------------------------------------------------


def _is_bundled():
    """Detect whether we're running as a compiled standalone executable."""
    if getattr(sys, 'frozen', False):
        return True  # PyInstaller
    exe_name = os.path.basename(sys.executable).lower()
    # In development, sys.executable is python.exe / pythonw.exe / python3.11.exe
    # When compiled (Nuitka), it's the custom exe name
    return not exe_name.startswith('python')


def get_app_root():
    """
    Return the application's persistent-data root directory.

    Bundled exe → directory containing the .exe
    Development  → current working directory (project root)
    """
    if _is_bundled():
        return os.path.dirname(sys.executable)
    return os.getcwd()


def get_cache_dir():
    """Return the cache directory path (absolute)."""
    return os.path.join(get_app_root(), "cache")


CONFIG_PATH = os.path.join(get_cache_dir(), "config.json")

DEFAULTS = {
    "api_key": "",
    "path": "",
    "only_chs": False,
    "remove_json": False,
    "use_remote_cache": True,
    "threads": 0,  # 0 = auto (CPU-based)
}


def load_config():
    """
    Load saved config, filling missing keys with defaults.
    Returns the config dict.
    """
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULTS)

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except (json.JSONDecodeError, IOError):
        return dict(DEFAULTS)

    # Merge with defaults (fills in any missing keys)
    config = dict(DEFAULTS)
    config.update(saved)
    return config


def save_config(config):
    """
    Save config dict to disk.
    Only persists known keys (ignores extras).
    """
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

    # Only save recognized keys
    cleaned = {k: config.get(k, DEFAULTS[k]) for k in DEFAULTS}

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)


def mask_api_key(api_key):
    """Return a masked version of the API key for display."""
    if not api_key or len(api_key) < 8:
        return "(not set)"
    return "*" * 8 + api_key[-4:]
