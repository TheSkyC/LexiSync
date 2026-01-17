# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QTreeWidget, QTreeWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QWidget, QTextEdit, QComboBox, QSplitter, QTableWidget, QTableWidgetItem
)
from PySide6.QtCore import Qt, Signal
import json
import uuid
import re
from copy import deepcopy
from utils.constants import EXTRACTION_PATTERN_PRESET_EXTENSION, DEFAULT_EXTRACTION_PATTERNS
from utils.localization import _
from services.code_file_service import unescape_overwatch_string


class ExtractionPatternTestDialog(QDialog):
    def __init__(self, parent, left_delim, right_delim, is_multiline):
        super().__init__(parent)
        self.left_delim = left_delim
        self.right_delim = right_delim
        self.is_multiline = is_multiline
        self.setWindowTitle(_("Extraction Rule Tester"))
        self.resize(800, 600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Vertical)

        # Input
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.addWidget(QLabel(_("Sample Text:")))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(_("Paste your code content here..."))
        input_layout.addWidget(self.input_edit)
        splitter.addWidget(input_widget)

        # Output
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.addWidget(QLabel(_("Extraction Results:")))
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(["#", _("Raw Match"), _("Processed Value")])
        self.result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        output_layout.addWidget(self.result_table)
        splitter.addWidget(output_widget)

        layout.addWidget(splitter)

        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton(_("Run Test"))
        self.btn_run.clicked.connect(self.run_test)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_run)
        layout.addLayout(btn_layout)

    def run_test(self):
        content = self.input_edit.toPlainText()
        if not content: return

        self.result_table.setRowCount(0)

        try:
            flags = re.DOTALL if self.is_multiline else 0
            full_regex = f"({self.left_delim})(.*?)({self.right_delim})"
            pattern = re.compile(full_regex, flags)

            matches = list(pattern.finditer(content))
            self.result_table.setRowCount(len(matches))

            for i, match in enumerate(matches):
                raw_content = match.group(2)
                processed = unescape_overwatch_string(raw_content)

                self.result_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                self.result_table.setItem(i, 1, QTableWidgetItem(repr(raw_content)))
                self.result_table.setItem(i, 2, QTableWidgetItem(processed))

        except re.error as e:
            QMessageBox.critical(self, _("Regex Error"), str(e))


class ExtractionPatternManagerDialog(QDialog):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.patterns_buffer = deepcopy(self.app.config.get("extraction_patterns", DEFAULT_EXTRACTION_PATTERNS))
        self.result = None

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(900, 600)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton(_("Add"))
        add_btn.clicked.connect(self.add_item)
        toolbar.addWidget(add_btn)

        delete_btn = QPushButton(_("Delete Selected"))
        delete_btn.clicked.connect(self.delete_item)
        toolbar.addWidget(delete_btn)

        reset_btn = QPushButton(_("Reset to Defaults"))
        reset_btn.clicked.connect(self.reset_to_defaults)
        toolbar.addWidget(reset_btn)

        toolbar.addStretch(1)

        import_btn = QPushButton(_("Import Preset"))
        import_btn.clicked.connect(self.import_preset)
        toolbar.addWidget(import_btn)

        export_btn = QPushButton(_("Export Preset"))
        export_btn.clicked.connect(self.export_preset)
        toolbar.addWidget(export_btn)
        main_layout.addLayout(toolbar)

        # Tree View
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(
            [_("Enabled"), _("Rule Name"), _("String Type"), _("Left Delimiter"), _("Right Delimiter")])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tree.setSelectionBehavior(QTreeWidget.SelectRows)
        self.tree.setDragDropMode(QTreeWidget.InternalMove)
        self.tree.itemDoubleClicked.connect(self.edit_item)
        main_layout.addWidget(self.tree)

        self.populate_tree()

        # Buttons
        button_box = QHBoxLayout()
        button_box.addStretch(1)
        ok_btn = QPushButton(_("OK"))
        ok_btn.clicked.connect(self.accept)
        button_box.addWidget(ok_btn)

        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_box.addWidget(cancel_btn)
        main_layout.addLayout(button_box)

    def populate_tree(self):
        self.tree.clear()
        for pattern in self.patterns_buffer:
            enabled_char = "✔" if pattern.get("enabled", True) else "✖"
            item = QTreeWidgetItem(self.tree, [
                enabled_char,
                pattern.get("name", _("Unnamed Rule")),
                pattern.get("string_type", _("Custom")),
                pattern.get("left_delimiter", ""),
                pattern.get("right_delimiter", "")
            ])
            item.setData(0, Qt.UserRole, pattern["id"])
            self.tree.addTopLevelItem(item)

    def get_current_order_from_tree(self):
        new_order = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item_id = item.data(0, Qt.UserRole)
            original_pattern = next((p for p in self.patterns_buffer if p["id"] == item_id), None)
            if original_pattern:
                new_order.append(original_pattern)
        self.patterns_buffer = new_order

    def add_item(self):
        new_pattern = {
            "id": str(uuid.uuid4()),
            "name": _("New Rule"),
            "enabled": True,
            "string_type": _("Custom"),
            "left_delimiter": "",
            "right_delimiter": '"',
            "multiline": True
        }

        dialog = ExtractionPatternItemEditor(self, _("Add Extraction Rule"), new_pattern)
        if dialog.exec():
            self.patterns_buffer.append(dialog.result)
            self.populate_tree()
            for i in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(i)
                if item.data(0, Qt.UserRole) == dialog.result["id"]:
                    self.tree.setCurrentItem(item)
                    self.tree.scrollToItem(item)
                    break

    def delete_item(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return
        selected_id = selected_items[0].data(0, Qt.UserRole)
        self.patterns_buffer = [p for p in self.patterns_buffer if p["id"] != selected_id]
        self.populate_tree()

    def edit_item(self, item, column):
        item_id = item.data(0, Qt.UserRole)
        pattern_to_edit = next((p for p in self.patterns_buffer if p["id"] == item_id), None)
        if not pattern_to_edit:
            return

        dialog = ExtractionPatternItemEditor(self, _("Edit Extraction Rule"), pattern_to_edit)
        if dialog.exec():
            for i, p_item in enumerate(self.patterns_buffer):
                if p_item["id"] == item_id:
                    self.patterns_buffer[i] = dialog.result
                    break
            self.populate_tree()

    def reset_to_defaults(self):
        reply = QMessageBox.question(self, _("Confirm"),
                                     _("Are you sure you want to reset extraction rules to their default settings?\nAll current custom rules will be lost."),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.patterns_buffer = deepcopy(DEFAULT_EXTRACTION_PATTERNS)
            self.populate_tree()

    def import_preset(self):
        filepath, selected_filter = QFileDialog.getOpenFileName(
            self,
            _("Import Extraction Rule Preset"),
            "",
            _("Extraction Pattern Files (*{ext});;All Files (*.*)").format(ext=EXTRACTION_PATTERN_PRESET_EXTENSION)
        )
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                preset = json.load(f)
            if isinstance(preset, list) and all("name" in p and "left_delimiter" in p for p in preset):
                for p_item in preset:
                    if "id" not in p_item: p_item["id"] = str(uuid.uuid4())
                    if "enabled" not in p_item: p_item["enabled"] = True
                    if "string_type" not in p_item: p_item["string_type"] = _("Custom")
                    if "right_delimiter" not in p_item: p_item["right_delimiter"] = '"'
                self.patterns_buffer = preset
                QMessageBox.information(self, _("Success"), _("Preset imported successfully."))
                self.populate_tree()
            else:
                QMessageBox.critical(self, _("Error"), _("Preset file format is incorrect."))
        except Exception as e:
            QMessageBox.critical(self, _("Import Failed"), _("Could not load preset file: {error}").format(error=e))

    def export_preset(self):
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self,
            _("Export Extraction Rule Preset"),
            "my_extraction_patterns.extract",
            _("Extraction Pattern Files (*{ext});;All Files (*.*)").format(ext=EXTRACTION_PATTERN_PRESET_EXTENSION)
        )
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.patterns_buffer, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, _("Success"), _("Preset exported successfully."))
        except Exception as e:
            QMessageBox.critical(self, _("Export Failed"), _("Could not save preset file: {error}").format(error=e))

    def accept(self):
        self.get_current_order_from_tree()
        if self.patterns_buffer != self.app.config.get("extraction_patterns", DEFAULT_EXTRACTION_PATTERNS):
            self.app.config["extraction_patterns"] = deepcopy(self.patterns_buffer)
            self.app.save_config()
            self.app.update_statusbar(_("Extraction rules updated. Consider reloading the text."))
            self.result = True
        else:
            self.result = False
        super().accept()

    def reject(self):
        self.result = False
        super().reject()


class ExtractionPatternItemEditor(QDialog):
    def __init__(self, parent, title, initial_data):
        super().__init__(parent)
        self.initial_data = initial_data
        self.result = None

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(700, 450)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Rule Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel(_("Rule Name:")))
        self.name_entry = QLineEdit(self.initial_data.get("name", ""))
        name_layout.addWidget(self.name_entry)
        self.enabled_checkbox = QCheckBox(_("Enable this rule"))
        self.enabled_checkbox.setChecked(self.initial_data.get("enabled", True))
        name_layout.addWidget(self.enabled_checkbox)
        main_layout.addLayout(name_layout)

        # String Type
        string_type_layout = QHBoxLayout()
        string_type_layout.addWidget(QLabel(_("String Type:")))
        self.string_type_entry = QLineEdit(self.initial_data.get("string_type", _("Custom")))
        string_type_layout.addWidget(self.string_type_entry)
        main_layout.addLayout(string_type_layout)

        # Left Delimiter
        main_layout.addWidget(QLabel(_("Left Delimiter (Regex):")))
        self.left_text_edit = QTextEdit(self.initial_data.get("left_delimiter", ""))
        self.left_text_edit.setFixedHeight(60)
        main_layout.addWidget(self.left_text_edit)

        # Right Delimiter
        main_layout.addWidget(QLabel(_("Right Delimiter (Regex):")))
        self.right_text_edit = QTextEdit(self.initial_data.get("right_delimiter", ""))
        self.right_text_edit.setFixedHeight(60)
        main_layout.addWidget(self.right_text_edit)

        # Options
        options_layout = QHBoxLayout()
        self.multiline_checkbox = QCheckBox(_("Allow Multi-line Content"))
        self.multiline_checkbox.setChecked(self.initial_data.get("multiline", True))
        self.multiline_checkbox.setToolTip(
            _("If unchecked, extraction will stop at the end of the line. Useful for INI files."))
        options_layout.addWidget(self.multiline_checkbox)
        options_layout.addStretch()
        main_layout.addLayout(options_layout)

        # Regex Escape Buttons
        button_frame = QHBoxLayout()
        escape_left_btn = QPushButton(_("Escape for Regex (Left)"))
        escape_left_btn.clicked.connect(lambda: self.convert_to_regex('left'))
        button_frame.addWidget(escape_left_btn)

        escape_right_btn = QPushButton(_("Escape for Regex (Right)"))
        escape_right_btn.clicked.connect(lambda: self.convert_to_regex('right'))
        button_frame.addWidget(escape_right_btn)

        test_btn = QPushButton(_("Test Rule..."))
        test_btn.clicked.connect(self.open_tester)
        button_frame.addWidget(test_btn)

        button_frame.addStretch(1)
        main_layout.addLayout(button_frame)

        # OK/Cancel Buttons
        dialog_buttons = QHBoxLayout()
        dialog_buttons.addStretch(1)
        ok_btn = QPushButton(_("OK"))
        ok_btn.clicked.connect(self.accept)
        dialog_buttons.addWidget(ok_btn)

        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        dialog_buttons.addWidget(cancel_btn)
        main_layout.addLayout(dialog_buttons)

    def convert_to_regex(self, target):
        text_edit = self.left_text_edit if target == 'left' else self.right_text_edit
        current_text = text_edit.toPlainText().strip()
        escaped_text = re.escape(current_text)
        text_edit.setPlainText(escaped_text)

    def open_tester(self):
        dialog = ExtractionPatternTestDialog(
            self,
            self.left_text_edit.toPlainText(),
            self.right_text_edit.toPlainText(),
            self.multiline_checkbox.isChecked()
        )
        dialog.exec()

    def accept(self):
        name = self.name_entry.text().strip()
        enabled = self.enabled_checkbox.isChecked()
        string_type = self.string_type_entry.text().strip() or _("Custom")
        left_delimiter = self.left_text_edit.toPlainText().strip()
        right_delimiter = self.right_text_edit.toPlainText().strip()
        multiline = self.multiline_checkbox.isChecked()

        if not name:
            QMessageBox.critical(self, _("Error"), _("Rule name cannot be empty."))
            return
        if not left_delimiter or not right_delimiter:
            QMessageBox.critical(self, _("Error"), _("Left and right delimiters cannot be empty."))
            return

        self.result = {
            "id": self.initial_data["id"],
            "name": name,
            "enabled": enabled,
            "string_type": string_type,
            "left_delimiter": left_delimiter,
            "right_delimiter": right_delimiter,
            "multiline": multiline
        }
        super().accept()

    def reject(self):
        self.result = None
        super().reject()