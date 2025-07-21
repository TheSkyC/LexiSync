# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sys
import subprocess
import logging
from importlib.metadata import version, PackageNotFoundError
from packaging.version import parse as parse_version
from packaging.specifiers import SpecifierSet

logger = logging.getLogger(__name__)


class DependencyManager:
    _instance = None

    @staticmethod
    def get_instance():
        if DependencyManager._instance is None:
            DependencyManager._instance = DependencyManager()
        return DependencyManager._instance

    def __init__(self):
        self._cache = {}

    def check_external_dependency(self, lib_name: str, specifier_str: str = "") -> dict:
        if lib_name in self._cache:
            return self._cache[lib_name]

        result = {
            'name': lib_name,
            'required': specifier_str,
            'installed': None,
            'status': 'missing'  # 'ok', 'missing', 'outdated'
        }

        try:
            installed_version_str = version(lib_name)
            result['installed'] = installed_version_str

            if not specifier_str:
                result['status'] = 'ok'
            else:
                spec = SpecifierSet(specifier_str)
                installed_version = parse_version(installed_version_str)
                if installed_version in spec:
                    result['status'] = 'ok'
                else:
                    result['status'] = 'outdated'

        except PackageNotFoundError:
            result['status'] = 'missing'

        self._cache[lib_name] = result
        return result

    def check_plugin_dependency(self, required_id: str, specifier_str: str, installed_plugins: dict) -> dict:
        """
        Checks a dependency on another plugin.
        """
        result = {
            'name': required_id,
            'required': specifier_str,
            'installed': None,
            'status': 'missing'
        }

        if required_id in installed_plugins:
            installed_plugin = installed_plugins[required_id]
            installed_version_str = installed_plugin.version()
            result['installed'] = installed_version_str

            if not specifier_str:
                result['status'] = 'ok'
            else:
                spec = SpecifierSet(specifier_str)
                installed_version = parse_version(installed_version_str)
                if installed_version in spec:
                    result['status'] = 'ok'
                else:
                    result['status'] = 'outdated'
        else:
            result['status'] = 'missing'

        return result

    def install_package(self, package_spec: str, progress_callback=None):
        """Installs a package using pip in a background thread."""
        # This should be run in a QThread to avoid blocking the UI
        try:
            command = [sys.executable, "-m", "pip", "install", "--upgrade", package_spec]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                       encoding='utf-8')

            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output and progress_callback:
                    progress_callback(output.strip())

            return process.poll() == 0
        except Exception as e:
            logger.error(f"Failed to install package {package_spec}: {e}", exc_info=True)
            if progress_callback:
                progress_callback(f"Error: {e}")
            return False