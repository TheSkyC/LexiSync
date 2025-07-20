# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton, QDialogButtonBox
from PySide6.QtCore import Qt
from .obfuscator_logic import ObfuscatorLogic


class ElementDialog(QDialog):
    def __init__(self, parent, code_content, last_value, translator):
        super().__init__(parent)
        self._ = translator
        self.code_content = code_content
        self.warning_threshold = 26000
        self.setWindowTitle(self._("Code Obfuscation"))
        self.setModal(True)
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        prompt_label = QLabel(
            self._("Please provide the total number of elements from the original code:") + \
            f"<br><small><i>{self._('How to get: In-game Workshop -> Show Diagnostics -> Total Element Count')}</i></small>"
        )
        prompt_label.setWordWrap(True)
        layout.addWidget(prompt_label)
        input_layout = QHBoxLayout()
        self.spinbox = QSpinBox()
        self.spinbox.setRange(1, 32767)
        self.spinbox.setSingleStep(500)
        self.spinbox.setValue(last_value)
        self.calc_button = QPushButton(self._("Auto-Calculate"))
        input_layout.addWidget(self.spinbox, 1)
        input_layout.addWidget(self.calc_button)
        layout.addLayout(input_layout)
        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(button_box)

        self.calc_button.clicked.connect(self.auto_calculate)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        self.spinbox.valueChanged.connect(self.update_hint_label)
        self.update_hint_label(self.spinbox.value())
    def auto_calculate(self):
        estimated_count = ObfuscatorLogic.estimate_element_count(self.code_content)
        self.spinbox.setValue(estimated_count)
    def get_element_count(self):
        return self.spinbox.value()
    def update_hint_label(self, value):
        if value > self.warning_threshold:
            self.hint_label.setText(
                f"<font color='orange'>{self._('Warning: High element count. This leaves little room for obfuscation and may cause errors.')}</font>"
            )
        elif value < 200:
            self.hint_label.setText(
                f"<font color='orange'>{self._('Hint: Low element count. Recommended minimum of 200.')}</font>"
            )
        else:
            self.hint_label.setText("")