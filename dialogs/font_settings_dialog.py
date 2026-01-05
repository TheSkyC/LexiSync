# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QSpinBox, QMessageBox, QGroupBox, QFontComboBox, QDialogButtonBox
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from utils.localization import _
from utils.config_manager import get_default_font_settings


class FontPickerWidget(QGroupBox):
    def __init__(self, title, initial_family, initial_size, parent=None):
        super().__init__(title, parent)
        self.initial_family = initial_family
        self.initial_size = initial_size

        layout = QVBoxLayout(self)

        # Family Input
        family_layout = QHBoxLayout()
        family_layout.addWidget(QLabel(_("Font Family:")))
        self.family_edit = QLineEdit(initial_family)
        self.family_edit.setPlaceholderText("e.g. Consolas, Microsoft YaHei")
        self.family_edit.setToolTip(
            _("Enter font families separated by commas. The first available font will be used."))
        family_layout.addWidget(self.family_edit)

        # Font Combo Helper
        self.font_combo = QFontComboBox()
        self.font_combo.setFixedWidth(120)
        self.font_combo.currentFontChanged.connect(self._append_font)
        family_layout.addWidget(self.font_combo)

        layout.addLayout(family_layout)

        # Size Input
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel(_("Size:")))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 72)
        self.size_spin.setValue(initial_size)
        size_layout.addWidget(self.size_spin)
        size_layout.addStretch()

        layout.addLayout(size_layout)

        # Preview
        self.preview_label = QLabel(_("Preview Text / 预览文本 / 123"))
        self.preview_label.setFixedHeight(40)
        self.preview_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.preview_label.setStyleSheet("border: 1px solid #DDD; padding: 5px; background: white;")
        layout.addWidget(self.preview_label)

        # Connect signals for preview
        self.family_edit.textChanged.connect(self._update_preview)
        self.size_spin.valueChanged.connect(self._update_preview)
        self._update_preview()

    def _append_font(self, font):
        current = self.family_edit.text().strip()
        new_family = font.family()
        if '"' in new_family or ' ' in new_family:
            new_family = f'"{new_family}"'

        if current:
            if new_family not in current:
                self.family_edit.setText(f"{current}, {new_family}")
        else:
            self.family_edit.setText(new_family)

    def _update_preview(self):
        families = self.family_edit.text().split(',')
        # Clean up quotes
        families = [f.strip().strip('"').strip("'") for f in families if f.strip()]

        font = QFont()
        if families:
            font.setFamilies(families)
        font.setPointSize(self.size_spin.value())

        self.preview_label.setFont(font)

    def get_data(self):
        return {
            "family": self.family_edit.text(),
            "size": self.size_spin.value()
        }

    def set_enabled_state(self, enabled):
        self.family_edit.setEnabled(enabled)
        self.font_combo.setEnabled(enabled)
        self.size_spin.setEnabled(enabled)


class FontSettingsDialog(QDialog):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.config = app_instance.config

        # Load or init settings
        self.settings = self.config.get("font_settings", get_default_font_settings())

        # Migration check (if old format)
        if "scripts" in self.settings:
            self.settings = get_default_font_settings()

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(500, 450)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.enable_check = QCheckBox(_("Enable Custom Fonts"))
        self.enable_check.setChecked(self.settings.get("enable_custom_fonts", False))
        self.enable_check.toggled.connect(self._toggle_widgets)
        layout.addWidget(self.enable_check)

        # UI Font
        ui_conf = self.settings.get("ui_font", {})
        self.ui_picker = FontPickerWidget(
            _("Application UI Font"),
            ui_conf.get("family", "Segoe UI"),
            ui_conf.get("size", 9)
        )
        layout.addWidget(self.ui_picker)

        # Editor Font
        editor_conf = self.settings.get("editor_font", {})
        self.editor_picker = FontPickerWidget(
            _("Translation Editor Font"),
            editor_conf.get("family", "Consolas"),
            editor_conf.get("size", 10)
        )
        layout.addWidget(self.editor_picker)

        layout.addStretch()

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        reset_button = QPushButton(_("Reset Defaults"))
        btn_box.addButton(reset_button, QDialogButtonBox.ResetRole)

        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        reset_button.clicked.connect(self.reset_defaults)

        layout.addWidget(btn_box)

        self._toggle_widgets(self.enable_check.isChecked())

    def _toggle_widgets(self, checked):
        self.ui_picker.set_enabled_state(checked)
        self.editor_picker.set_enabled_state(checked)

    def reset_defaults(self):
        defaults = get_default_font_settings()
        self.enable_check.setChecked(False)

        d_ui = defaults["ui_font"]
        self.ui_picker.family_edit.setText(d_ui["family"])
        self.ui_picker.size_spin.setValue(d_ui["size"])

        d_ed = defaults["editor_font"]
        self.editor_picker.family_edit.setText(d_ed["family"])
        self.editor_picker.size_spin.setValue(d_ed["size"])

    def accept(self):
        new_settings = {
            "enable_custom_fonts": self.enable_check.isChecked(),
            "ui_font": self.ui_picker.get_data(),
            "editor_font": self.editor_picker.get_data()
        }

        self.config["font_settings"] = new_settings
        self.app.save_config()

        super().accept()