# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from plugins.plugin_base import PluginBase
from .obfuscator_dialog import ObfuscatorDialog
from .obfuscator_logic import ObfuscatorLogic
from .element_dialog import ElementDialog
from PySide6.QtWidgets import QMessageBox, QApplication, QFileDialog, QInputDialog
import logging


class ObfuscatorPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.config_key = "string_obfuscator_settings"
        self.config = self.get_default_config()

    def get_default_config(self):
        return {
            'remember_settings': True,
            'last_element_count': 1000,
            'complexity': 50,
            'obfuscate_rules': True,
            'obfuscate_strings': True,
            'remove_comments': True,
            'remove_rule_names': True,
        }

    def setup(self, main_window, plugin_manager):
        super().setup(main_window, plugin_manager)
        self.load_config()

    def plugin_id(self) -> str:
        return "com_theskyc_obfuscator"

    def name(self) -> str:
        return self._("OW Code Obfuscator")

    def description(self) -> str:
        return self._(
            "Obfuscate Overwatch Workshop code. "
            "Features include string obfuscation, rule padding, and removal of comments and rule names. "
            "Some features Currently only supports code written in Chinese or English."
        )

    def version(self) -> str:
        return "1.0.2"

    def author(self) -> str:
        return "TheSkyC"

    def url(self) -> str:
        return "https://github.com/TheSkyC/lexisync/tree/master/plugins/com_theskyc_obfuscator"

    def add_menu_items(self) -> list:
        return [
            (self.name(), [
                (self._("Obfuscate Current File"), self.obfuscate_current_file),
                (self._("Obfuscate Specific File..."), self.obfuscate_specific_files),
                (self._("Obfuscator Settings..."), lambda checked=False: self.show_settings_dialog(self.main_window)
                )
            ])
        ]



    def obfuscate_current_file(self):
        if not self.main_window.original_raw_code_content:
            QMessageBox.warning(self.main_window, self._("No Code"), self._("Please open a workshop code file first."))
            return
        self._start_obfuscation_flow(self.main_window.original_raw_code_content)

    def obfuscate_specific_files(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            self._("Select Workshop File to Obfuscate"),
            self.main_window.config.get("last_dir", ""),
            f"{self._('Workshop Files')} (*.ow *.txt);;{self._('All Files')} (*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._start_obfuscation_flow(content)
        except Exception as e:
            QMessageBox.critical(self.main_window, self._("Error"),
                                 self._("Failed to read file: {error}").format(error=e))

    def show_settings_dialog(self, parent_widget):
        dialog = ObfuscatorDialog(parent_widget, self.config, self._, is_settings_only=True)
        if dialog.exec():
            options, remember = dialog.get_options()
            self.config.update(options)
            self.config['remember_settings'] = remember
            self.save_config()
            self.main_window.update_statusbar(self._("Obfuscator settings saved."))
            return True
        return False

    def _start_obfuscation_flow(self, code_content):
        options_dialog = ObfuscatorDialog(self.main_window, self.config, self._)
        if not options_dialog.exec():
            return
        options = options_dialog.get_options()
        element_count = 0
        needs_element_count = options.get('obfuscate_rules') or \
                              options.get('obfuscate_indices') or \
                              options.get('obfuscate_local_indices')
        if needs_element_count:
            last_count = self.config.get('last_element_count', 1000)
            element_dialog = ElementDialog(self.main_window, code_content, last_count, self._)

            if not element_dialog.exec():
                return
            element_count = element_dialog.get_element_count()
        self.config.update(options)
        if needs_element_count:
            self.config['last_element_count'] = element_count
        self.save_config()
        try:
            self.main_window.update_statusbar(self._("Obfuscating code..."), persistent=True)
            QApplication.processEvents()

            logic = ObfuscatorLogic(code_content, options, element_count)
            obfuscated_code = logic.run()

            QApplication.clipboard().setText(obfuscated_code)
            self.main_window.update_statusbar("")
            QMessageBox.information(
                self.main_window,
                self._("Obfuscation Complete"),
                self._("The obfuscated code has been copied to your clipboard.")
            )
        except Exception as e:
            self.logger.error(f"Obfuscation process failed: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, self._("Obfuscation Error"), str(e))