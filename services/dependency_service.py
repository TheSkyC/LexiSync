# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import subprocess
import logging
from importlib.metadata import version, PackageNotFoundError
from packaging.version import parse as parse_version
from packaging.specifiers import SpecifierSet
from utils.path_utils import get_plugin_libs_path

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
        if not getattr(sys, 'frozen', False):
            try:
                import pip._internal.cli.main as pip_main

                command_args = [
                                   "install",
                                   "--target", libs_path,
                                   "--no-cache-dir",
                                   "--upgrade"
                               ] + deps_to_install

                if progress_callback:
                    progress_callback(f"Running pip internally with args: {command_args}")
                from io import StringIO
                import contextlib

                stdout_capture = StringIO()
                stderr_capture = StringIO()

                with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                    result = pip_main.main(command_args)
                if progress_callback:
                    progress_callback(stdout_capture.getvalue())
                    if stderr_capture.getvalue():
                        progress_callback(f"Errors:\n{stderr_capture.getvalue()}")
                if result != 0:
                    error_msg = f"Dependency installation failed with exit code {result}."
                    logger.error(error_msg)
                    if progress_callback: progress_callback(error_msg)
                    return False
                if progress_callback:
                    progress_callback("Dependencies installed successfully!")
                self._cache.clear()
                return True
            except Exception as e:
                error_msg = f"An error occurred while running pip internally: {e}"
                logger.error(error_msg, exc_info=True)
                if progress_callback: progress_callback(error_msg)
                return False
        else:
            python_executable = sys.executable
            command = [
                          python_executable,
                          '--install-deps'
                      ] + deps_to_install

            if progress_callback:
                progress_callback(f"Running command: {' '.join(command)}")

            try:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                           encoding='utf-8',
                                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)

                for stdout_line in iter(process.stdout.readline, ""):
                    if progress_callback:
                        progress_callback(stdout_line.strip())

                stderr_output = process.communicate()[1]

                if process.returncode != 0:
                    error_msg = f"Dependency installation failed!\n\nError:\n{stderr_output}"
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