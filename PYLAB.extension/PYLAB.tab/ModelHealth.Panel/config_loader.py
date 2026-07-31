"""Shared JSON config loader for ModelHealth panel tools.

Reads JSON configs from pushbutton folders (team/standard settings,
committed to git) and from %APPDATA% (personal preferences).
"""

import json
import os


def get_appdata_dir(tool_name):
    """Return per-user config directory for a tool.

    Example: %APPDATA%/pyRevit/PYLAB/Bypass/
    """
    base = os.path.join(os.environ.get("APPDATA", ""), "pyRevit", "PYLAB", tool_name)
    return base


def load_json(file_path, default=None):
    """Load a JSON file. Returns default (or empty dict) if missing or invalid."""
    if not os.path.isfile(file_path):
        if default is not None:
            return default
        return {}

    try:
        with open(file_path, "r") as fh:
            return json.load(fh)
    except (ValueError, IOError):
        if default is not None:
            return default
        return {}


def save_json(file_path, data):
    """Save data as JSON. Creates parent directories if needed."""
    parent = os.path.dirname(file_path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(file_path, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)


def load_team_config(button_dir, config_filename, default=None):
    """Load a team/standard config from a pushbutton folder.

    Example:
        load_team_config(__file__, 'naming_standards.json')
        loads from same directory as the calling script.
    """
    if os.path.isfile(button_dir):
        button_dir = os.path.dirname(button_dir)
    file_path = os.path.join(button_dir, config_filename)
    return load_json(file_path, default)


def load_user_config(tool_name, config_filename, default=None):
    """Load a personal preferences JSON from %APPDATA%.

    Example:
        load_user_config('FamilyShortcut', 'shortcuts.json')
        loads from %APPDATA%/pyRevit/PYLAB/FamilyShortcut/shortcuts.json
    """
    file_path = os.path.join(get_appdata_dir(tool_name), config_filename)
    return load_json(file_path, default)


def save_user_config(tool_name, config_filename, data):
    """Save a personal preferences JSON to %APPDATA%."""
    file_path = os.path.join(get_appdata_dir(tool_name), config_filename)
    save_json(file_path, data)


def save_team_config(button_dir, config_filename, data):
    """Save a team/standard config JSON next to a pushbutton script."""
    if os.path.isfile(button_dir):
        button_dir = os.path.dirname(button_dir)
    file_path = os.path.join(button_dir, config_filename)
    save_json(file_path, data)
