# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import logging
import os

IS_DEBUG_MODE = False


def setup_debug_mode():
    global IS_DEBUG_MODE  # noqa: PLW0603
    debug_env_var = os.getenv("DEBUG", "0").lower()
    if debug_env_var in ("1", "true", "on", "yes"):
        IS_DEBUG_MODE = True


def get_logger(name):
    return logging.getLogger(name)
