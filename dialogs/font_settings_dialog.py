# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QSpinBox, QMessageBox, QWidget, QComboBox, QTabWidget
)
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtCore import Qt
from utils.localization import _
from utils.config_manager import get_default_font_settings


class FontSettingsDialog(QDialog):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.config = app_instance.config
        self.font_settings_buffer = self.config["font_settings"].copy()

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(600, 450)

        self.available_fonts = sorted(QFontDatabase().families())

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        self.override_checkbox = QCheckBox(_("Override default font settings"))
        self.override_checkbox.setChecked(self.font_settings_buffer["override_default_fonts"])
        self.override_checkbox.stateChanged.connect(self.toggle_controls)
        main_layout.addWidget(self.override_checkbox)

        self.notebook = QTabWidget()
        main_layout.addWidget(self.notebook)

        self.script_tabs = {}
        scripts = self.font_settings_buffer["scripts"]
        for script_name, settings in scripts.items():
            frame = QWidget()
            self.notebook.addTab(frame, script_name.capitalize())
            self.create_font_selector(frame, script_name, settings)

        code_frame = QWidget()
        self.notebook.addTab(code_frame, _("Code Context"))
        self.create_font_selector(code_frame, "code_context", self.font_settings_buffer["code_context"])

        button_frame = QHBoxLayout()
        reset_btn = QPushButton(_("Reset to Defaults"))
        reset_btn.clicked.connect(self.reset_to_defaults)
        button_frame.addWidget(reset_btn)
        button_frame.addStretch(1)

        ok_btn = QPushButton(_("OK"))
        ok_btn.clicked.connect(self.accept)
        button_frame.addWidget(ok_btn)

        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_frame.addWidget(cancel_btn)
        main_layout.addLayout(button_frame)

        self.toggle_controls()

    def create_font_selector(self, parent_widget, script_name, settings):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Font Family
        family_layout = QHBoxLayout()
        family_layout.addWidget(QLabel(_("Font Family:")))
        family_combo = QComboBox()
        family_combo.addItems(self.available_fonts)
        family_combo.setCurrentText(settings["family"])
        family_layout.addWidget(family_combo)
        layout.addLayout(family_layout)

        # Size
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel(_("Size:")))
        size_spin = QSpinBox()
        size_spin.setRange(6, 72)
        size_spin.setValue(settings["size"])
        size_layout.addWidget(size_spin)
        size_layout.addStretch(1)
        layout.addLayout(size_layout)

        # Style
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel(_("Style:")))
        style_combo = QComboBox()
        style_combo.addItems(["normal", "bold", "italic", "bold italic"])
        style_combo.setCurrentText(settings["style"])
        style_layout.addWidget(style_combo)
        style_layout.addStretch(1)
        layout.addLayout(style_layout)

        layout.addStretch(1)

        self.script_tabs[script_name] = {
            "frame": parent_widget,
            "family_combo": family_combo,
            "size_spin": size_spin,
            "style_combo": style_combo
        }

    def toggle_controls(self):
        enabled = self.override_checkbox.isChecked()
        for script_name, controls in self.script_tabs.items():
            controls["family_combo"].setEnabled(enabled)
            controls["size_spin"].setEnabled(enabled)
            controls["style_combo"].setEnabled(enabled)

    def reset_to_defaults(self):
        reply = QMessageBox.question(self, _("Confirmation"), _("Reset all font settings to default?"),
                               QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            default_settings = get_default_font_settings()
            self.font_settings_buffer = default_settings.copy()
            self.override_checkbox.setChecked(default_settings["override_default_fonts"])
            for script, controls in self.script_tabs.items():
                if script in default_settings["scripts"]:
                    settings = default_settings["scripts"][script]
                elif script == "code_context":
                    settings = default_settings["code_context"]
                else:
                    continue
                controls["family_combo"].setCurrentText(settings["family"])
                controls["size_spin"].setValue(settings["size"])
                controls["style_combo"].setCurrentText(settings["style"])
            self.toggle_controls()

    def accept(self):
        new_settings = self.font_settings_buffer.copy()
        new_settings["override_default_fonts"] = self.override_checkbox.isChecked()
        for script, controls in self.script_tabs.items():
            if script in new_settings["scripts"]:
                target = new_settings["scripts"][script]
            elif script == "code_context":
                target = new_settings["code_context"]
            else:
                continue
            target["family"] = controls["family_combo"].currentText()
            target["size"] = controls["size_spin"].value()
            target["style"] = controls["style_combo"].currentText()

        self.config["font_settings"] = new_settings
        self.app.save_config()
        super().accept()

    def reject(self):
        super().reject()