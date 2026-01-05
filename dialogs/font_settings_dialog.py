# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSpinBox, QMessageBox, QGroupBox, QFontComboBox,
    QDialogButtonBox, QListWidget, QListWidgetItem, QFrame
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, Signal
from utils.localization import _
from utils.config_manager import get_default_font_settings
from ui_components.styled_button import StyledButton


class FontPickerWidget(QGroupBox):
    fontChanged = Signal()

    def __init__(self, title, initial_family_str, initial_size, parent=None):
        super().__init__(title, parent)
        # Parse initial string "Font A, Font B" -> ["Font A", "Font B"]
        self.font_families = [
            f.strip().strip('"').strip("'")
            for f in initial_family_str.split(',')
            if f.strip()
        ]
        self.initial_size = initial_size

        self.setup_ui()
        self.refresh_list()
        self._update_preview()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Top Area: Add Font ---
        add_layout = QHBoxLayout()
        add_layout.setContentsMargins(0, 0, 0, 0)

        self.font_combo = QFontComboBox()
        self.font_combo.setEditable(False)  # Prevent random typing
        # Filter out vertical fonts (@font) which are usually garbage on Windows
        self.font_combo.setFontFilters(QFontComboBox.AllFonts)

        self.add_btn = StyledButton(_("Add"), on_click=self._add_font, btn_type="success", size="small")

        add_layout.addWidget(QLabel(_("Select Font:")))
        add_layout.addWidget(self.font_combo, 1)
        add_layout.addWidget(self.add_btn)

        layout.addLayout(add_layout)

        # --- Middle Area: List & Ordering ---
        list_layout = QHBoxLayout()

        self.font_list = QListWidget()
        self.font_list.setMaximumHeight(120)
        self.font_list.setToolTip(
            _("Fonts are used in order. If the first font doesn't support a character, the next one is used."))
        self.font_list.currentRowChanged.connect(self._on_selection_changed)
        self.font_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #DCDFE6;
                border-radius: 4px;
                background-color: #FFFFFF;
                outline: 0;
            }
            QListWidget::item {
                padding: 3px 8px;
                border-bottom: 1px solid #F0F0F0;
                color: #333333;
            }
            QListWidget::item:selected {
                background-color: #E6F7FF;
                color: #409EFF;
                border-bottom: 1px solid #BAE7FF;
            }
            QListWidget::item:hover:!selected {
                background-color: #F5F7FA;
            }
        """)

        # Action Buttons (Right side of list)
        btn_col = QVBoxLayout()
        btn_col.setSpacing(5)

        self.move_up_btn = StyledButton("↑", on_click=self._move_up, size="small",
                                        tooltip=_("Move Up (Higher Priority)"))
        self.move_down_btn = StyledButton("↓", on_click=self._move_down, size="small",
                                          tooltip=_("Move Down (Lower Priority)"))
        self.remove_btn = StyledButton("✕", on_click=self._remove_font, btn_type="danger", size="small",
                                       tooltip=_("Remove Font"))

        btn_col.addWidget(self.move_up_btn)
        btn_col.addWidget(self.move_down_btn)
        btn_col.addWidget(self.remove_btn)
        btn_col.addStretch()

        list_layout.addWidget(self.font_list, 1)
        list_layout.addLayout(btn_col)

        layout.addLayout(list_layout)

        # --- Bottom Area: Size & Preview ---
        bottom_layout = QHBoxLayout()

        # Size
        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 72)
        self.size_spin.setValue(self.initial_size)
        self.size_spin.setSuffix(" pt")
        self.size_spin.valueChanged.connect(self._on_font_changed)

        bottom_layout.addWidget(QLabel(_("Size:")))
        bottom_layout.addWidget(self.size_spin)
        bottom_layout.addStretch()

        layout.addLayout(bottom_layout)

        # Preview Label (Using QLabel to avoid ghosting issues)
        self.preview_label = QLabel(_("Preview Text / 预览文本 / 123 ABC xyz"))
        self.preview_label.setFixedHeight(60)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                border: 1px solid #DCDFE6;
                border-radius: 4px;
                background-color: #FFFFFF;
                color: #333333;
            }
        """)
        layout.addWidget(self.preview_label)

        # Initial State
        self._on_selection_changed(-1)

    def refresh_list(self):
        self.font_list.clear()
        for family in self.font_families:
            self.font_list.addItem(QListWidgetItem(family))

    def _add_font(self):
        font = self.font_combo.currentFont()
        family = font.family()

        # Avoid duplicates
        if family in self.font_families:
            return

        self.font_families.append(family)
        self.refresh_list()
        # Select the new item
        self.font_list.setCurrentRow(self.font_list.count() - 1)
        self._on_font_changed()

    def _remove_font(self):
        row = self.font_list.currentRow()
        if row >= 0:
            self.font_families.pop(row)
            self.refresh_list()
            # Try to keep selection valid
            if row < self.font_list.count():
                self.font_list.setCurrentRow(row)
            elif self.font_list.count() > 0:
                self.font_list.setCurrentRow(self.font_list.count() - 1)
            self._on_font_changed()

    def _move_up(self):
        row = self.font_list.currentRow()
        if row > 0:
            self.font_families[row], self.font_families[row - 1] = self.font_families[row - 1], self.font_families[row]
            self.refresh_list()
            self.font_list.setCurrentRow(row - 1)
            self._on_font_changed()

    def _move_down(self):
        row = self.font_list.currentRow()
        if row < len(self.font_families) - 1:
            self.font_families[row], self.font_families[row + 1] = self.font_families[row + 1], self.font_families[row]
            self.refresh_list()
            self.font_list.setCurrentRow(row + 1)
            self._on_font_changed()

    def _on_selection_changed(self, row):
        has_selection = row >= 0
        count = len(self.font_families)

        self.remove_btn.setEnabled(has_selection)
        self.move_up_btn.setEnabled(has_selection and row > 0)
        self.move_down_btn.setEnabled(has_selection and row < count - 1)

    def _on_font_changed(self):
        self._update_preview()
        self.fontChanged.emit()

    def _update_preview(self):
        font = QFont()
        # QFont takes a list of strings directly, no quotes needed
        if self.font_families:
            font.setFamilies(self.font_families)

        font.setPointSize(self.size_spin.value())
        self.preview_label.setFont(font)

    def get_data(self):
        # Join with commas. We don't add quotes here to keep data clean.
        # Quotes are only needed when generating CSS strings.
        return {
            "family": ", ".join(self.font_families),
            "size": self.size_spin.value()
        }

    def set_enabled_state(self, enabled):
        self.font_combo.setEnabled(enabled)
        self.add_btn.setEnabled(enabled)
        self.font_list.setEnabled(enabled)
        self.size_spin.setEnabled(enabled)
        # Update buttons based on selection if enabled
        if enabled:
            self._on_selection_changed(self.font_list.currentRow())
        else:
            self.remove_btn.setEnabled(False)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)


class FontSettingsDialog(QDialog):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.config = app_instance.config
        self.settings_changed = False

        # Load settings
        self.settings = self.config.get("font_settings", get_default_font_settings())
        # Migration check
        if "scripts" in self.settings:
            self.settings = get_default_font_settings()

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(550, 650)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Enable Checkbox
        self.enable_check = QCheckBox(_("Enable Custom Fonts"))
        self.enable_check.setChecked(self.settings.get("enable_custom_fonts", False))
        self.enable_check.toggled.connect(self._toggle_widgets)
        self.enable_check.toggled.connect(self._mark_changed)
        layout.addWidget(self.enable_check)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # UI Font Picker
        ui_conf = self.settings.get("ui_font", {})
        self.ui_picker = FontPickerWidget(
            _("Application UI Font"),
            ui_conf.get("family", "Segoe UI"),
            ui_conf.get("size", 9)
        )
        self.ui_picker.fontChanged.connect(self._mark_changed)
        layout.addWidget(self.ui_picker)

        # Editor Font Picker
        editor_conf = self.settings.get("editor_font", {})
        self.editor_picker = FontPickerWidget(
            _("Translation Editor Font"),
            editor_conf.get("family", "Consolas"),
            editor_conf.get("size", 10)
        )
        self.editor_picker.fontChanged.connect(self._mark_changed)
        layout.addWidget(self.editor_picker)

        layout.addStretch()

        # Buttons
        btn_box = QDialogButtonBox()

        # Apply
        apply_btn = StyledButton(_("Apply"), on_click=self._apply_settings, btn_type="success")
        btn_box.addButton(apply_btn, QDialogButtonBox.ApplyRole)

        # OK / Cancel
        ok_btn = StyledButton(_("OK"), on_click=self._on_accept, btn_type="primary")
        cancel_btn = StyledButton(_("Cancel"), on_click=self._on_reject, btn_type="default")
        btn_box.addButton(ok_btn, QDialogButtonBox.AcceptRole)
        btn_box.addButton(cancel_btn, QDialogButtonBox.RejectRole)

        # Reset
        reset_btn = StyledButton(_("Reset Defaults"), on_click=self._reset_defaults, btn_type="warning")
        btn_box.addButton(reset_btn, QDialogButtonBox.ResetRole)

        layout.addWidget(btn_box)

        self._toggle_widgets(self.enable_check.isChecked())

    def _toggle_widgets(self, checked):
        self.ui_picker.set_enabled_state(checked)
        self.editor_picker.set_enabled_state(checked)

    def _mark_changed(self):
        self.settings_changed = True

    def _reset_defaults(self):
        reply = QMessageBox.question(
            self,
            _("Reset to Defaults"),
            _("Are you sure you want to reset all font settings to defaults?"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            defaults = get_default_font_settings()
            self.enable_check.setChecked(False)

            # Reset UI Picker
            d_ui = defaults["ui_font"]
            self.ui_picker.font_families = [f.strip() for f in d_ui["family"].split(',')]
            self.ui_picker.size_spin.setValue(d_ui["size"])
            self.ui_picker.refresh_list()
            self.ui_picker._update_preview()

            # Reset Editor Picker
            d_ed = defaults["editor_font"]
            self.editor_picker.font_families = [f.strip() for f in d_ed["family"].split(',')]
            self.editor_picker.size_spin.setValue(d_ed["size"])
            self.editor_picker.refresh_list()
            self.editor_picker._update_preview()

            self._mark_changed()

    def _apply_settings(self):
        new_settings = {
            "enable_custom_fonts": self.enable_check.isChecked(),
            "ui_font": self.ui_picker.get_data(),
            "editor_font": self.editor_picker.get_data()
        }

        self.config["font_settings"] = new_settings
        self.app.save_config()

        # Apply changes immediately
        if hasattr(self.app, '_apply_custom_fonts'):
            self.app._apply_custom_fonts()
        if hasattr(self.app, '_update_editor_fonts'):
            self.app._update_editor_fonts()

        self.settings_changed = False
        self.app.update_statusbar(_("Font settings applied."))

    def _on_accept(self):
        self._apply_settings()
        super().accept()

    def _on_reject(self):
        if self.settings_changed:
            reply = QMessageBox.question(
                self,
                _("Unsaved Changes"),
                _("You have unsaved changes. Do you want to discard them?"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                super().reject()
        else:
            super().reject()