# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QTreeWidget, QTreeWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QWidget, QTextEdit, QComboBox, QGroupBox, QTextBrowser,
    QAbstractItemView, QSizePolicy, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QEvent, QSize
import json
import uuid
from copy import deepcopy
from ui_components.tooltip import Tooltip
from utils.constants import PROMPT_PRESET_EXTENSION, DEFAULT_PROMPT_STRUCTURE, STRUCTURAL, STATIC, DYNAMIC
from utils.localization import _


class WrappingTextBrowser(QTextBrowser):
    placeholder_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().contentsChanged.connect(self.updateGeometry)
        self._original_html = ""

    def setHtml(self, html):
        self._original_html = html
        super().setHtml(html)

    def setSource(self, name):
        if name.toString():
            self.placeholder_clicked.emit(name.toString())


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            anchor = self.anchorAt(event.pos())
            if anchor:
                self.placeholder_clicked.emit(anchor)
                return
        super().mousePressEvent(event)

    def sizeHint(self) -> QSize:
        self.document().setTextWidth(self.viewport().width())
        doc_height = self.document().size().height()
        margins = self.contentsMargins()
        frame_width = self.frameWidth() * 2
        required_height = doc_height + margins.top() + margins.bottom() + frame_width
        return QSize(super().sizeHint().width(), int(required_height))

    def resizeEvent(self, event: QSize) -> None:
        super().resizeEvent(event)
        self.updateGeometry()


class PromptManagerDialog(QDialog):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.prompts_data = deepcopy(self.app.config.get("ai_prompts", []))

        self.current_prompt_index = 0

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(1000, 700)

        self.setup_ui()
        self.load_current_prompt_to_tree()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Preset Management
        preset_group = QGroupBox(_("Preset Management"))
        preset_layout = QHBoxLayout(preset_group)

        self.preset_combo = QComboBox()
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        self.update_preset_combo()

        add_btn = QPushButton(_("New"))
        add_btn.clicked.connect(self.add_new_preset)

        del_btn = QPushButton(_("Delete"))
        del_btn.clicked.connect(self.delete_current_preset)

        rename_btn = QPushButton(_("Rename/Type"))
        rename_btn.clicked.connect(self.edit_current_preset_meta)

        preset_layout.addWidget(QLabel(_("Current Preset:")))
        preset_layout.addWidget(self.preset_combo, 1)
        preset_layout.addWidget(add_btn)
        preset_layout.addWidget(rename_btn)
        preset_layout.addWidget(del_btn)

        main_layout.addWidget(preset_group)

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
        self.tree.model().rowsMoved.connect(self.sync_data_from_tree)
        main_layout.addWidget(self.tree)


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
            enabled_char = "✓" if part.get("enabled", True) else "✗"
            display_type = self.get_display_type(part["type"])
            item = QTreeWidgetItem(self.tree, [
                enabled_char,
                display_type,
                part["content"]
            ])
            item.setData(0, Qt.UserRole, part["id"])
            item.setFlags(item.flags() & ~Qt.ItemIsDropEnabled)
            self.tree.addTopLevelItem(item)

    def sync_data_from_tree(self):
        new_order = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item_id = item.data(0, Qt.UserRole)
            original_part = next((p for p in self.prompt_structure if p["id"] == item_id), None)
            if original_part:
                new_order.append(original_part)
        self.prompt_structure = new_order

    def update_tree_item(self, item_id, updated_data):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.data(0, Qt.UserRole) == item_id:
                enabled_char = "✓" if updated_data.get("enabled", True) else "✗"
                display_type = self.get_display_type(updated_data["type"])
                item.setText(0, enabled_char)
                item.setText(1, display_type)
                item.setText(2, updated_data["content"])
                break

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

    def update_preset_combo(self):
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        for p in self.prompts_data:
            type_str = _("Translation") if p.get("type") == "translation" else _("Correction")
            self.preset_combo.addItem(f"{p['name']} ({type_str})", p['id'])

        if 0 <= self.current_prompt_index < len(self.prompts_data):
            self.preset_combo.setCurrentIndex(self.current_prompt_index)
        self.preset_combo.blockSignals(False)

    def on_preset_changed(self, index):
        if index < 0: return
        # 切换前先保存当前树的数据到内存中的 list
        self.save_tree_to_current_memory()
        self.current_prompt_index = index
        self.load_current_prompt_to_tree()

    def load_current_prompt_to_tree(self):
        if not self.prompts_data:
            self.tree.clear()
            return

        current_data = self.prompts_data[self.current_prompt_index]
        self.prompt_structure = current_data["structure"]  # 绑定当前操作的结构
        self.populate_tree()  # 复用原有的 populate_tree

    def save_tree_to_current_memory(self):
        if not self.prompts_data: return
        # sync_data_from_tree 会更新 self.prompt_structure
        # 我们需要确保 self.prompt_structure 指向的是 self.prompts_data 中的正确对象
        self.sync_data_from_tree()
        self.prompts_data[self.current_prompt_index]["structure"] = self.prompt_structure

    def add_new_preset(self):
        # 简单实现：复制当前预设
        if not self.prompts_data: return
        new_preset = deepcopy(self.prompts_data[self.current_prompt_index])
        new_preset["id"] = str(uuid.uuid4())
        new_preset["name"] = new_preset["name"] + " (Copy)"
        self.prompts_data.append(new_preset)
        self.save_tree_to_current_memory()  # 保存当前状态
        self.current_prompt_index = len(self.prompts_data) - 1
        self.update_preset_combo()
        self.load_current_prompt_to_tree()

    def delete_current_preset(self):
        if len(self.prompts_data) <= 1:
            QMessageBox.warning(self, _("Warning"), _("At least one preset must remain."))
            return

        reply = QMessageBox.question(self, _("Confirm Delete"), _("Are you sure you want to delete this preset?"))
        if reply == QMessageBox.Yes:
            self.prompts_data.pop(self.current_prompt_index)
            self.current_prompt_index = max(0, self.current_prompt_index - 1)
            self.update_preset_combo()
            self.load_current_prompt_to_tree()

    def edit_current_preset_meta(self):
        # 这里应该弹出一个对话框修改 Name 和 Type，简化起见只修改 Name
        current = self.prompts_data[self.current_prompt_index]
        new_name, ok = QInputDialog.getText(self, _("Rename Preset"), _("Preset Name:"), text=current["name"])
        if ok and new_name:
            current["name"] = new_name

            # 询问类型
            types = ["translation", "correction"]
            type_item, ok_type = QInputDialog.getItem(
                self, _("Preset Type"), _("Select Usage Type:"),
                [_("Translation"), _("Correction")],
                0 if current.get("type") == "translation" else 1,
                False
            )
            if ok_type:
                current["type"] = "translation" if type_item == _("Translation") else "correction"

            self.update_preset_combo()

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
        self.sync_data_from_tree()

        item_id = item.data(0, Qt.UserRole)
        part_to_edit = next((p for p in self.prompt_structure if p["id"] == item_id), None)
        if not part_to_edit:
            return

        placeholders_data = [
            {'placeholder': '[Source Text]', 'description': _('The original text to be translated.'),
             'provider': _('Main App')},
            {'placeholder': '[Translation]', 'description': _('The current translation text.'),
             'provider': _('Main App')},
            {'placeholder': '[Error List]',
             'description': _('List of validation errors found in the current translation.'),
             'provider': _('Main App')},
            {'placeholder': '[Target Language]', 'description': _('The target language for translation.'),
             'provider': _('Main App')},
            {'placeholder': '[Glossary]',
             'description': _('Injects glossary terms found in the original text to enforce specific translations.'),
             'provider': _('Main App')},
            {'placeholder': '[Untranslated Context]', 'description': _('Nearby untranslated original text.'),
             'provider': _('Main App')},
            {'placeholder': '[Translated Context]', 'description': _('Nearby translated text for context.'),
             'provider': _('Main App')},
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
            self.update_tree_item(item_id, dialog.result)

    def reset_to_defaults(self):
        reply = QMessageBox.question(self, _("Confirm"),
                                     _("Are you sure you want to reset the prompt to its default settings?\nAll current customizations will be lost."),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.prompt_structure = deepcopy(DEFAULT_PROMPT_STRUCTURE)
            self.populate_tree()

    def import_preset(self):
        filepath, selected_filter = QFileDialog.getOpenFileName(
            self,
            _("Import Prompt Preset"),
            "",
            _("Prompt Files (*{ext});;All Files (*.*)").format(ext=PROMPT_PRESET_EXTENSION)
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
            "my_prompt_preset.prompt",
            _("Prompt Files (*{ext});;All Files (*.*)").format(ext=PROMPT_PRESET_EXTENSION)
        )
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.prompt_structure, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, _("Success"), _("Preset exported successfully."))
        except Exception as e:
            QMessageBox.critical(self, _("Export Failed"), _("Could not save preset file: {error}").format(error=e))

    def on_rows_moved(self, parent, start, end, destination, row):
        self.sync_data_from_tree()

    def accept(self):
        self.save_tree_to_current_memory()
        self.app.config["ai_prompts"] = self.prompts_data
        trans_preset = next((p for p in self.prompts_data if p.get("type") == "translation"), None)
        if trans_preset:
            self.app.config["ai_prompt_structure"] = trans_preset["structure"]

        self.app.save_config()
        self.app.update_statusbar(_("AI prompts updated."))
        super(QDialog, self).accept()

    def reject(self):
        super().reject()


class PromptItemEditor(QDialog):
    def __init__(self, parent, title, initial_data, placeholders_data=None):
        super().__init__(parent)
        self.initial_data = initial_data
        self.placeholders_data = placeholders_data or []
        self.result = None

        self.tooltip = Tooltip(self)
        self._last_hovered_anchor = ""

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(600, 400)

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
        content_label = QLabel(_("Content:"))
        main_layout.addWidget(content_label)

        self.content_text_edit = QTextEdit()
        self.content_text_edit.setAcceptRichText(False)
        self.content_text_edit.setPlainText(self.initial_data.get("content", ""))
        main_layout.addWidget(self.content_text_edit, 1)

        # Placeholders
        if self.placeholders_data:
            placeholders_group = QGroupBox(_("Available Placeholders (Click to Insert)"))
            placeholders_layout = QVBoxLayout(placeholders_group)

            # [CRITICAL UI CHOICE]
            # We use QLabel instead of QTextBrowser here.
            # QTextBrowser has a built-in navigation behavior on anchor clicks that is hard to suppress,
            # often causing the widget content to clear or reload when a link is clicked.
            # QLabel with openExternalLinks=False provides a safer way to handle link clicks via signals.
            # ---------------------------------------------------------------------------
            self.placeholders_browser = QLabel(self)
            self.placeholders_browser.setWordWrap(True)
            self.placeholders_browser.setTextFormat(Qt.RichText)
            self.placeholders_browser.setOpenExternalLinks(False)
            self.placeholders_browser.setTextInteractionFlags(Qt.TextBrowserInteraction)
            self.placeholders_browser.setMouseTracking(True)
            self.placeholders_browser.installEventFilter(self)

            self.placeholders_browser.linkActivated.connect(self.insert_placeholder_text)

            self.placeholders_browser.setStyleSheet("""
                QLabel { 
                    border: 1px solid #ccc;
                    background-color: #f9f9f9; 
                    font-size: 13px;
                    padding: 8px;
                    border-radius: 4px;
                }
            """)

            html_parts = []
            for data in self.placeholders_data:
                placeholder = data['placeholder']
                html_parts.append(
                    f'<a href="{placeholder}" style="color: #007BFF; text-decoration: none; background-color: #EAF2F8; padding: 2px 5px; border-radius: 3px; margin: 2px; display: inline-block;">{placeholder}</a>'
                )
            self.placeholders_browser.setText(" ".join(html_parts))

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

    def insert_placeholder_text(self, placeholder_text: str):
        self.content_text_edit.insertPlainText(placeholder_text)
        self.content_text_edit.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.placeholders_browser:
            if event.type() == QEvent.MouseMove:
                from PySide6.QtGui import QTextDocument, QTextCursor
                from PySide6.QtCore import QPoint
                local_pos = event.pos()
                doc = QTextDocument()
                doc.setDefaultFont(self.placeholders_browser.font())
                doc.setHtml(self.placeholders_browser.text())
                doc.setTextWidth(self.placeholders_browser.width())
                margins = self.placeholders_browser.contentsMargins()
                adjusted_pos = QPoint(local_pos.x() - margins.left(),
                                      local_pos.y() - margins.top())
                cursor_pos = doc.documentLayout().hitTest(adjusted_pos, Qt.FuzzyHit)

                anchor = ""
                if cursor_pos >= 0:
                    cursor = QTextCursor(doc)
                    cursor.setPosition(cursor_pos)
                    fmt = cursor.charFormat()

                    if fmt.isAnchor():
                        anchor = fmt.anchorHref()

                if anchor:
                    if anchor != self._last_hovered_anchor:
                        self._last_hovered_anchor = anchor
                        placeholder_data = next((p for p in self.placeholders_data if p['placeholder'] == anchor), None)
                        if placeholder_data:
                            tooltip_text = (
                                f"<b>{placeholder_data['placeholder']}</b><br>"
                                f"<hr style='border-color: #555; margin: 4px 0;'>"
                                f"<b>{_('Provider')}:</b> {placeholder_data.get('provider', 'N/A')}<br>"
                                f"<b>{_('Description')}:</b> {placeholder_data['description']}"
                            )
                            self.tooltip.show_tooltip(event.globalPos(), tooltip_text)
                        else:
                            self.tooltip.hide()
                else:
                    if self._last_hovered_anchor:
                        self._last_hovered_anchor = ""
                        self.tooltip.hide()

            elif event.type() == QEvent.Leave:
                self._last_hovered_anchor = ""
                self.tooltip.hide()

        return super().eventFilter(obj, event)

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