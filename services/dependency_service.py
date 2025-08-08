# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import subprocess
from importlib.metadata import version, PackageNotFoundError
from packaging.version import parse as parse_version
from packaging.specifiers import SpecifierSet
from utils.path_utils import get_plugin_libs_path
from utils.plugin_context import plugin_libs_context
import logging
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
            'status': 'missing'
        }
        with plugin_libs_context():
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

    def install_dependencies(self, dependencies: dict, progress_callback=None):
        if not dependencies:
            if progress_callback:
                progress_callback("Plugin has no external dependencies.")
            return True

        libs_path = get_plugin_libs_path()
        deps_to_install = [f"{name}{spec}" for name, spec in dependencies.items()]
        python_executable = sys.executable
        command = []
        if not getattr(sys, 'frozen', False):
            # 开发环境：直接调用 pip
            command = [
                          python_executable, "-m", "pip", "install",
                          "--target", libs_path,
                          "--no-cache-dir", "--upgrade", "--no-user"
                      ] + deps_to_install
        else:
            # 编译环境
            base_path = os.path.dirname(sys.executable)
            python_executable = os.path.join(base_path, 'python.exe')
            if not os.path.exists(python_executable):
                error_msg = "FATAL: Bundled python.exe not found. Cannot install dependencies."
                logger.error(error_msg)
                if progress_callback: progress_callback(error_msg)
                return False
            command = [
                          python_executable, "-m", "pip", "install",
                          "--target", libs_path,
                          "--no-cache-dir", "--upgrade", "--no-user"
                      ] + deps_to_install

        if progress_callback:
            progress_callback(f"Running command: {' '.join(command)}")
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            for line in iter(process.stdout.readline, ''):
                if progress_callback:
                    progress_callback(line.strip())
            process.wait()
            if process.returncode != 0:
                error_msg = f"Dependency installation failed with exit code {process.returncode}."
                logger.error(error_msg)
                if progress_callback: progress_callback(error_msg)
                return False

            if progress_callback:
                progress_callback("Dependencies installed successfully!")
            self._cache.clear()
            return True
        except Exception as e:
            error_msg = f"An unknown error occurred while running subprocess: {e}"
            logger.error(error_msg, exc_info=True)
            if progress_callback: progress_callback(error_msg)
            return False