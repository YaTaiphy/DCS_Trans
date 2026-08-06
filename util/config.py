"""
Persistent Configuration

Saves and loads user preferences (API key, path, options) as defaults
so users don't have to re-enter them every session.

Stored at ./cache/config.json (gitignored — contains API key).
"""

import os
import json

CONFIG_PATH = "./cache/config.json"

DEFAULTS = {
    "api_key": "",
    "path": "",
    "only_chs": False,
    "remove_json": False,
    "use_remote_cache": True,
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
