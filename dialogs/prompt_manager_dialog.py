# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QTreeWidget, QTreeWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QWidget, QTextEdit, QComboBox, QGroupBox, QTextBrowser,
    QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
import json
import uuid
from copy import deepcopy
from utils.constants import PROMPT_PRESET_EXTENSION, DEFAULT_PROMPT_STRUCTURE, STRUCTURAL, STATIC, DYNAMIC
from utils.localization import _

class PromptManagerDialog(QDialog):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.prompt_structure = deepcopy(self.app.config.get("ai_prompt_structure", DEFAULT_PROMPT_STRUCTURE))
        self.result = None

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(1000, 700)

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
        self.tree.setHeaderLabels([_("Enabled"), _("Type"), _("Content")])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tree.setSelectionBehavior(QTreeWidget.SelectRows)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)

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
        for part in self.prompt_structure:
            enabled_char = "✔" if part.get("enabled", True) else "✖"
            display_type = self.get_display_type(part["type"])
            item = QTreeWidgetItem(self.tree, [
                enabled_char,
                display_type,
                part["content"]
            ])
            item.setData(0, Qt.UserRole, part["id"])
            self.tree.addTopLevelItem(item)

    def get_display_type(self, internal_type):
        if internal_type == STRUCTURAL: return _("Structural Content")
        if internal_type == STATIC: return _("Static Instruction")
        if internal_type == DYNAMIC: return _("Dynamic Instruction")
        return internal_type

    def get_internal_type(self, display_type):

        if display_type == _("Structural Content"): return STRUCTURAL
        if display_type == _("Static Instruction"): return STATIC
        if display_type == _("Dynamic Instruction"): return DYNAMIC
        return display_type

    def get_current_order_from_tree(self):
        new_order = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item_id = item.data(0, Qt.UserRole)
            original_part = next((p for p in self.prompt_structure if p["id"] == item_id), None)
            if original_part:
                new_order.append(original_part)
        self.prompt_structure = new_order

    def add_item(self):
        new_part = {"id": str(uuid.uuid4()), "type": STATIC, "enabled": True, "content": _("New Instruction")}
        dialog = PromptItemEditor(self, _("Add Prompt Fragment"), new_part)
        if dialog.exec():
            self.prompt_structure.append(dialog.result)
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
        self.prompt_structure = [p for p in self.prompt_structure if p["id"] != selected_id]
        self.populate_tree()

    def edit_item(self, item, column):
        item_id = item.data(0, Qt.UserRole)
        part_to_edit = next((p for p in self.prompt_structure if p["id"] == item_id), None)
        if not part_to_edit:
            return
        placeholders_data = [
            {'placeholder': '[Target Language]', 'description': _('The target language for translation.'), 'provider': _('Main App')},
            {'placeholder': '[Untranslated Context]', 'description': _('Nearby untranslated original text.'), 'provider': _('Main App')},
            {'placeholder': '[Translated Context]', 'description': _('Nearby translated text for context.'), 'provider': _('Main App')},
        ]
        plugin_placeholders = self.app.plugin_manager.run_hook('register_ai_placeholders')
        if plugin_placeholders:
            placeholders_data.extend(plugin_placeholders)
        dialog = PromptItemEditor(self, _("Edit Prompt Fragment"), part_to_edit, placeholders_data)
        if dialog.exec():
            for i, p_item in enumerate(self.prompt_structure):
                if p_item["id"] == item_id:
                    self.prompt_structure[i] = dialog.result
                    break
            self.populate_tree()

    def reset_to_defaults(self):
        reply = QMessageBox.question(self, _("Confirm"), _("Are you sure you want to reset the prompt to its default settings?\nAll current customizations will be lost."),
                               QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.prompt_structure = deepcopy(DEFAULT_PROMPT_STRUCTURE)
            self.populate_tree()

    def import_preset(self):
        filepath, selected_filter = QFileDialog.getOpenFileName(
            self,
            _("Import Prompt Preset"),
            "",
            _("Overwatch Prompt Files (*{ext});;All Files (*.*)").format(ext=PROMPT_PRESET_EXTENSION)
        )
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                preset = json.load(f)
            if isinstance(preset, list) and all("content" in p for p in preset):
                for p_item in preset:
                    if "id" not in p_item: p_item["id"] = str(uuid.uuid4())
                    if "enabled" not in p_item: p_item["enabled"] = True
                    if "type" not in p_item: p_item["type"] = STATIC
                self.prompt_structure = preset
                self.populate_tree()
                QMessageBox.information(self, _("Success"), _("Preset imported successfully."))
            else:
                QMessageBox.critical(self, _("Error"), _("Preset file format is incorrect."))
        except Exception as e:
            QMessageBox.critical(self, _("Import Failed"), _("Could not load preset file: {error}").format(error=e))

    def export_preset(self):
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self,
            _("Export Prompt Preset"),
            "my_prompt_preset.owprompt",
            _("Overwatch Prompt Files (*{ext});;All Files (*.*)").format(ext=PROMPT_PRESET_EXTENSION)
        )
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.prompt_structure, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, _("Success"), _("Preset exported successfully."))
        except Exception as e:
            QMessageBox.critical(self, _("Export Failed"), _("Could not save preset file: {error}").format(error=e))

    def accept(self):
        self.get_current_order_from_tree()
        self.app.config["ai_prompt_structure"] = self.prompt_structure
        self.app.save_config()
        self.app.update_statusbar(_("AI prompt structure updated."))
        super().accept()

    def reject(self):
        super().reject()


class PromptItemEditor(QDialog):
    def __init__(self, parent, title, initial_data, placeholders_data=None):
        super().__init__(parent)
        self.initial_data = initial_data
        self.placeholders_data = placeholders_data or []
        self.result = None

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(600, 350)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel(_("Type:")))
        self.type_combo = QComboBox()
        self.display_values = {
            STRUCTURAL: _("Structural Content"),
            STATIC: _("Static Instruction"),
            DYNAMIC: _("Dynamic Instruction")
        }
        self.type_combo.addItems(list(self.display_values.values()))
        self.type_combo.setCurrentText(self.display_values.get(self.initial_data["type"], self.initial_data["type"]))
        type_layout.addWidget(self.type_combo)

        self.enabled_checkbox = QCheckBox(_("Enable this fragment"))
        self.enabled_checkbox.setChecked(self.initial_data.get("enabled", True))
        type_layout.addWidget(self.enabled_checkbox)
        type_layout.addStretch(1)
        main_layout.addLayout(type_layout)

        # Content editor
        main_layout.addWidget(QLabel(_("Content:")))
        self.content_text_edit = QTextEdit(self.initial_data["content"])
        main_layout.addWidget(self.content_text_edit)

        # Placeholders
        if self.placeholders_data:
            placeholders_group = QGroupBox(_("Available Placeholders (Click to Insert)"))
            placeholders_layout = QVBoxLayout(placeholders_group)
            self.placeholders_browser = QTextBrowser(self)
            self.placeholders_browser.setOpenExternalLinks(False)  # 我们自己处理点击
            self.placeholders_browser.setReadOnly(True)
            self.placeholders_browser.anchorClicked.connect(self.insert_placeholder_from_url)
            self.placeholders_browser.setStyleSheet("""
                QTextBrowser { 
                    border: none; 
                    background-color: transparent; 
                    font-size: 13px;
                }
            """)
            doc_height = self.placeholders_browser.document().size().height()
            self.placeholders_browser.setMaximumHeight(int(doc_height) + 10)

            html_parts = []
            for data in self.placeholders_data:
                placeholder = data['placeholder']
                description = data['description']
                provider = data.get('provider', _('Unknown'))
                tooltip_text = f"{_('Provider')}: {provider}\n{_('Description')}: {description}"

                html_parts.append(
                    f'<a href="{placeholder}" title="{tooltip_text}" style="color: #007BFF; text-decoration: none; background-color: #EAF2F8; padding: 2px 5px; border-radius: 3px; margin: 2px;">{placeholder}</a>'
                )
            self.placeholders_browser.setHtml(" ".join(html_parts))
            placeholders_layout.addWidget(self.placeholders_browser)
            main_layout.addWidget(placeholders_group)

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

    def insert_placeholder_from_url(self, url):
        self.content_text_edit.insertPlainText(url.toDisplayString())

    def accept(self):
        selected_display_value = self.type_combo.currentText()
        internal_key = self.initial_data["type"]
        for key, display_val in self.display_values.items():
            if display_val == selected_display_value:
                internal_key = key
                break

        self.result = {
            "id": self.initial_data["id"],
            "type": internal_key,
            "enabled": self.enabled_checkbox.isChecked(),
            "content": self.content_text_edit.toPlainText().strip()
        }
        super().accept()

    def reject(self):
        self.result = None
        super().reject()