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


def get_plugin_libs_path():
    if platform.system() == "Windows":
        base_path = os.environ.get('LOCALAPPDATA')
        if not base_path:
            base_path = os.environ.get('APPDATA')
    elif platform.system() == "Darwin":
        base_path = os.path.expanduser('~/Library/Application Support')
    else:
        base_path = os.path.expanduser('~/.local/share')
    app_data_path = os.path.join(base_path, "LexiSync")
    libs_path = os.path.join(app_data_path, "plugin_libs")
    os.makedirs(libs_path, exist_ok=True)
    return libs_path