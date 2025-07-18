# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QComboBox, QCheckBox, QDoubleSpinBox, QLineEdit, \
    QDialogButtonBox, QGroupBox

class SettingsDialog(QDialog):
    def __init__(self, parent, current_settings, translator):
        super().__init__(parent)
        self._ = translator
        self.setWindowTitle(self._("Pseudo-Localization Settings"))
        self.setModal(True)
        self.settings = current_settings.copy()

        layout = QVBoxLayout(self)

        # General Settings
        general_group = QGroupBox(self._("General Settings"))
        form_layout = QFormLayout(general_group)

        self.auto_pseudo_checkbox = QCheckBox(self._("Auto pseudo-localize on apply"))
        self.auto_pseudo_checkbox.setToolTip(
            self._("When enabled, any text applied as a translation (manually, from TM, or AI) will be automatically converted.")
        )
        self.auto_pseudo_checkbox.setChecked(self.settings['auto_pseudo_on_apply'])
        form_layout.addRow(self.auto_pseudo_checkbox)

        self.mode_combo = QComboBox()

        self.mode_map = {
            'basic': self._("Basic"),
            'comprehensive': self._("Comprehensive"),
            'extreme': self._("Extreme")
        }
        for internal_name, display_name in self.mode_map.items():
            self.mode_combo.addItem(display_name, internal_name)
        current_mode_internal = self.settings.get('mode', 'comprehensive')
        index_to_set = self.mode_combo.findData(current_mode_internal)
        if index_to_set != -1:
            self.mode_combo.setCurrentIndex(index_to_set)
        form_layout.addRow(self._("Processing Mode:"), self.mode_combo)

        self.expansion_checkbox = QCheckBox(self._("Enable length expansion"))
        self.expansion_checkbox.setChecked(self.settings['length_expansion'])
        form_layout.addRow(self.expansion_checkbox)

        self.expansion_factor_spinbox = QDoubleSpinBox()
        self.expansion_factor_spinbox.setRange(1.0, 3.0)
        self.expansion_factor_spinbox.setSingleStep(0.1)
        self.expansion_factor_spinbox.setValue(self.settings['expansion_factor'])
        form_layout.addRow(self._("Expansion Factor:"), self.expansion_factor_spinbox)

        self.unicode_checkbox = QCheckBox(self._("Enable Unicode character replacement"))
        self.unicode_checkbox.setChecked(self.settings['unicode_replacement'])
        form_layout.addRow(self.unicode_checkbox)

        layout.addWidget(general_group)

        # Preservation Settings
        preserve_group = QGroupBox(self._("Preservation Settings"))
        preserve_layout = QFormLayout(preserve_group)

        self.placeholders_checkbox = QCheckBox(self._("Preserve {placeholders}"))
        self.placeholders_checkbox.setChecked(self.settings['preserve_placeholders'])
        preserve_layout.addRow(self.placeholders_checkbox)

        self.html_checkbox = QCheckBox(self._("Preserve HTML tags"))
        self.html_checkbox.setChecked(self.settings['preserve_html'])
        preserve_layout.addRow(self.html_checkbox)

        self.urls_checkbox = QCheckBox(self._("Preserve URLs and emails"))
        self.urls_checkbox.setChecked(self.settings['preserve_urls'])
        preserve_layout.addRow(self.urls_checkbox)

        layout.addWidget(preserve_group)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        self.settings['auto_pseudo_on_apply'] = self.auto_pseudo_checkbox.isChecked()
        self.settings['mode'] = self.mode_combo.currentData()
        self.settings['length_expansion'] = self.expansion_checkbox.isChecked()
        self.settings['expansion_factor'] = self.expansion_factor_spinbox.value()
        self.settings['unicode_replacement'] = self.unicode_checkbox.isChecked()
        self.settings['preserve_placeholders'] = self.placeholders_checkbox.isChecked()
        self.settings['preserve_html'] = self.html_checkbox.isChecked()
        self.settings['preserve_urls'] = self.urls_checkbox.isChecked()
        super().accept()

    def get_settings(self):
        return self.settings