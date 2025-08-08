# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sys
import os
import platform


def get_resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_app_data_path() -> str:
    """
    Returns the root directory for application data (configs, plugins, TM).
    - Windows: C:/Users/User/AppData/Local/LexiSync
    - macOS: ~/Library/Application Support/LexiSync
    - Linux: ~/.local/share/LexiSync
    """
    if platform.system() == "Windows":
        base_path = os.environ.get('LOCALAPPDATA')
        if not base_path:
            base_path = os.environ.get('APPDATA')
    elif platform.system() == "Darwin":  # macOS
        base_path = os.path.expanduser('~/Library/Application Support')
    else:  # Linux and other Unix
        base_path = os.path.expanduser('~/.local/share')

    app_data_path = os.path.join(base_path, "LexiSync")
    os.makedirs(app_data_path, exist_ok=True)
    return app_data_path

def get_plugin_libs_path() -> str:
    app_data_path = get_app_data_path()
    libs_path = os.path.join(app_data_path, "plugin_libs")
    os.makedirs(libs_path, exist_ok=True)
    return libs_path