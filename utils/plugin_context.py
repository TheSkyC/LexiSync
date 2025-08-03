# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sys
import threading
from contextlib import contextmanager
from typing import Set
from .path_utils import get_plugin_libs_path

_thread_local = threading.local()

def _get_context_depth() -> int:
    return getattr(_thread_local, 'context_depth', 0)

def _set_context_depth(depth: int):
    _thread_local.context_depth = depth

def _get_added_paths() -> Set[str]:
    if not hasattr(_thread_local, 'added_paths'):
        _thread_local.added_paths = set()
    return _thread_local.added_paths

@contextmanager
def plugin_libs_context():
    libs_path = get_plugin_libs_path()
    current_depth = _get_context_depth()
    added_paths = _get_added_paths()

    path_was_added = False
    if libs_path not in sys.path and libs_path not in added_paths:
        sys.path.insert(0, libs_path)
        added_paths.add(libs_path)
        path_was_added = True

    _set_context_depth(current_depth + 1)

    try:
        yield
    finally:
        new_depth = _get_context_depth() - 1
        _set_context_depth(new_depth)
        if new_depth == 0 and path_was_added:
            try:
                sys.path.remove(libs_path)
                added_paths.discard(libs_path)
            except ValueError:
                pass


def require_plugin_libs(func):
    def wrapper(*args, **kwargs):
        with plugin_libs_context():
            return func(*args, **kwargs)

    return wrapper