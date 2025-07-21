# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QDialogButtonBox, QGroupBox, QSlider, QLabel, QHBoxLayout
from PySide6.QtCore import Qt


class ObfuscatorDialog(QDialog):
    def __init__(self, parent, config, translator, is_settings_only = False):
        super().__init__(parent)
        self._ = translator
        self.config = config.copy()

        if is_settings_only:
            self.setWindowTitle(self._("Obfuscator Settings"))
            ok_button_text = self._("Save")
        else:
            self.setWindowTitle(self._("Code Obfuscation"))
            ok_button_text = self._("Start Obfuscation")
        self.setModal(True)
        self.resize(500, 250)

        layout = QVBoxLayout(self)

        options_group = QGroupBox(self._("Obfuscation Options"))
        options_layout = QVBoxLayout(options_group)

        self.options_map = {
            'obfuscate_rules': self._("Pad with Fake Rules"),
            'obfuscate_strings': self._("Obfuscate Strings"),
            'remove_comments': self._("Remove Comments"),
            'remove_rule_names': self._("Remove Rule Names"),
            'obfuscate_variables': self._("Obfuscate Variables & Subroutines (UNSTABLE)")
        }

        self.checkboxes = {}
        defaults = {
            'obfuscate_rules': True,
            'obfuscate_strings': True,
            'remove_comments': True,
            'remove_rule_names': True,
            'obfuscate_variables': False
        }

        for key, text in self.options_map.items():
            checkbox = QCheckBox(text)
            checkbox.setChecked(self.config.get(key, defaults.get(key, True)))
            self.checkboxes[key] = checkbox
            options_layout.addWidget(checkbox)

        layout.addWidget(options_group)

        complexity_group = QGroupBox(self._("Complexity Settings"))
        complexity_layout = QHBoxLayout(complexity_group)

        self.complexity_slider = QSlider(Qt.Horizontal)
        self.complexity_slider.setRange(1, 100)
        self.complexity_slider.setValue(self.config.get('complexity', 50))

        self.complexity_label = QLabel(f"{self.complexity_slider.value()}%")
        self.complexity_label.setFixedWidth(40)

        self.complexity_slider.valueChanged.connect(lambda val: self.complexity_label.setText(f"{val}%"))

        complexity_layout.addWidget(QLabel(self._("Complexity:")))
        complexity_layout.addWidget(self.complexity_slider)
        complexity_layout.addWidget(self.complexity_label)
        layout.addWidget(complexity_group)

        button_box = QDialogButtonBox()
        self.ok_button = button_box.addButton(ok_button_text, QDialogButtonBox.AcceptRole)
        button_box.addButton(QDialogButtonBox.Cancel)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_options(self):
        selected = {key: cb.isChecked() for key, cb in self.checkboxes.items()}
        selected['complexity'] = self.complexity_slider.value()
        return selected