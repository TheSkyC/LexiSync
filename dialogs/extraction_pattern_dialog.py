# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QTreeWidget, QTreeWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QWidget, QTextEdit, QComboBox, QSplitter, QTableView,
    QGroupBox, QRadioButton, QButtonGroup, QMenu, QAbstractItemView,
    QSizePolicy, QPlainTextEdit
)
from PySide6.QtCore import Qt, Signal, QTimer, QAbstractTableModel, QModelIndex, QEvent
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QAction, QTextCursor
import json
import uuid
import re
import time
import bisect
from copy import deepcopy


from ui_components.tooltip import Tooltip
from dialogs.ai_regex_generator_dialog import AIRegexGeneratorDialog
from utils.constants import EXTRACTION_PATTERN_PRESET_EXTENSION, DEFAULT_EXTRACTION_PATTERNS
from utils.localization import _
from services.code_file_service import unescape_overwatch_string


# --- 语法高亮器 ---
class RegexHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.matches = []
        self.match_starts = []

        self.fmt_match = QTextCharFormat()
        self.fmt_match.setBackground(QColor("#E8F5E9"))
        self.fmt_match.setForeground(QColor("#2E7D32"))

        self.fmt_conflict = QTextCharFormat()
        self.fmt_conflict.setBackground(QColor("#FFEBEE"))
        self.fmt_conflict.setForeground(QColor("#C62828"))
        self.fmt_conflict.setFontUnderline(True)

    def set_matches(self, matches):
        self.matches = matches
        self.match_starts = [m['start'] for m in matches]
        self.rehighlight()

    def highlightBlock(self, text):
        if not self.matches:
            return

        block_start = self.currentBlock().position()
        block_len = len(text)
        block_end = block_start + block_len

        start_index = bisect.bisect_right(self.match_starts, block_start)
        if start_index > 0:
            start_index -= 1

        for i in range(start_index, len(self.matches)):
            m = self.matches[i]
            m_start = m['start']
            m_end = m['end']

            if m_start >= block_end:
                break
            if m_end <= block_start:
                continue

            rel_start = max(0, m_start - block_start)
            rel_end = min(block_len, m_end - block_start)
            length = rel_end - rel_start

            if length > 0:
                fmt = self.fmt_conflict if m.get('is_conflict') else self.fmt_match
                self.setFormat(rel_start, length, fmt)


# --- 数据模型 ---
class ExtractionResultModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._headers = [_("Rule"), _("Raw Match"), _("Processed Value"), _("Pos"), _("Status")]

    def set_data(self, new_data):
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        item = self._data[row]

        if role == Qt.DisplayRole:
            if col == 0: return item['rule_name']
            if col == 1:
                raw = item['raw']
                return raw[:50] + "..." if len(raw) > 50 else raw
            if col == 2:
                proc = item['processed']
                return proc[:50] + "..." if len(proc) > 50 else proc
            if col == 3: return f"{item['start']}-{item['end']}"
            if col == 4: return _("Conflict") if item['is_conflict'] else _("OK")

        elif role == Qt.ForegroundRole:
            if col == 4:
                return QColor("red") if item['is_conflict'] else QColor("green")

        elif role == Qt.FontRole:
            if col == 4 and item['is_conflict']:
                font = QFont()
                font.setBold(True)
                return font

        elif role == Qt.UserRole:
            return item

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None


# --- 测试对话框 ---
class ExtractionPatternTestDialog(QDialog):
    def __init__(self, parent, rules, initial_rule_id=None, sample_text=""):
        super().__init__(parent)
        self.rules = rules
        self.initial_rule_id = initial_rule_id
        self.setWindowTitle(_("Extraction Rule Tester"))
        self.resize(1000, 700)

        self._is_highlighting = False
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(300)
        self.debounce_timer.timeout.connect(self.run_test)

        self.tooltip = Tooltip(self)
        self._last_hovered_index = QModelIndex()

        self.setup_ui()

        if sample_text:
            self.input_edit.setPlainText(sample_text)

        if self.initial_rule_id:
            self.rb_single.setChecked(True)
            index = self.combo_rules.findData(self.initial_rule_id)
            if index >= 0:
                self.combo_rules.setCurrentIndex(index)
        else:
            self.rb_all.setChecked(True)

        QTimer.singleShot(100, self.run_test)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. 控制面板
        control_group = QGroupBox(_("Test Configuration"))
        control_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        control_layout = QHBoxLayout(control_group)
        control_layout.setContentsMargins(10, 5, 10, 5)

        self.rb_all = QRadioButton(_("All Enabled Rules"))
        self.rb_single = QRadioButton(_("Specific Rule"))

        self.bg_scope = QButtonGroup(self)
        self.bg_scope.addButton(self.rb_all)
        self.bg_scope.addButton(self.rb_single)

        self.combo_rules = QComboBox()
        self.combo_rules.setEnabled(False)
        for rule in self.rules:
            name = rule.get("name", "Unnamed")
            if not rule.get("enabled", True):
                name += f" ({_('Disabled')})"
            self.combo_rules.addItem(name, rule["id"])

        self.rb_all.toggled.connect(self._on_scope_changed)
        self.rb_single.toggled.connect(self._on_scope_changed)
        self.combo_rules.currentIndexChanged.connect(self.trigger_run_test)

        control_layout.addWidget(self.rb_all)
        control_layout.addWidget(self.rb_single)
        control_layout.addWidget(self.combo_rules, 1)

        layout.addWidget(control_group)

        # 2. 主体分割
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：输入
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.addWidget(QLabel(_("Sample Text:")))
        self.input_edit = QPlainTextEdit()
        self.input_edit.textChanged.connect(self.trigger_run_test)
        input_layout.addWidget(self.input_edit)

        self.highlighter = RegexHighlighter(self.input_edit.document())

        splitter.addWidget(input_widget)

        # 右侧：结果
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(_("Extraction Results:")))
        self.lbl_stats = QLabel("")
        self.lbl_stats.setStyleSheet("color: gray; font-size: 11px;")
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_stats)
        output_layout.addLayout(header_layout)

        self.result_view = QTableView()
        self.result_model = ExtractionResultModel(self)
        self.result_view.setModel(self.result_model)

        self.result_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.result_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.result_view.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.result_view.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.result_view.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.result_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.result_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_view.clicked.connect(self._on_table_item_clicked)

        self.result_view.setMouseTracking(True)
        self.result_view.viewport().installEventFilter(self)
        output_layout.addWidget(self.result_view)

        splitter.addWidget(output_widget)
        splitter.setSizes([400, 600])

        layout.addWidget(splitter)

        # 3. 底部按钮
        btn_layout = QHBoxLayout()
        self.btn_export = QPushButton(_("Export Results..."))
        self.btn_export.clicked.connect(self.export_results)
        btn_close = QPushButton(_("Close"))
        btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_export)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def eventFilter(self, obj, event):
        if obj == self.result_view.viewport():
            if event.type() == QEvent.MouseMove:
                index = self.result_view.indexAt(event.pos())
                if index.isValid():
                    if index != self._last_hovered_index:
                        self._last_hovered_index = index
                        self._show_custom_tooltip(index, event.globalPos())
                else:
                    self.tooltip.hide()
                    self._last_hovered_index = QModelIndex()

            elif event.type() == QEvent.Leave:
                self.tooltip.hide()
                self._last_hovered_index = QModelIndex()

        return super().eventFilter(obj, event)

    def _show_custom_tooltip(self, index, global_pos):
        col = index.column()
        if col not in [1, 2]:
            self.tooltip.hide()
            return

        match_data = self.result_model.data(index, Qt.UserRole)
        if not match_data: return

        text = match_data['raw'] if col == 1 else match_data['processed']

        # Format content
        display_text = text[:2000] + "..." if len(text) > 2000 else text
        import html
        safe_text = html.escape(display_text).replace('\n', '<br>')

        title = _("Raw Match") if col == 1 else _("Processed Value")
        color = "#2E7D32" if col == 2 else "#0277BD"

        tooltip_html = (
            f"<b style='color:{color}'>{title}</b>"
            f"<hr style='margin:5px 0; border-color:#ccc;'>"
            f"<div style='font-family:Consolas; font-size:12px;'>{safe_text}</div>"
        )

        self.tooltip.show_tooltip(global_pos, tooltip_html)

    def _on_scope_changed(self):
        is_single = self.rb_single.isChecked()
        self.combo_rules.setEnabled(is_single)
        self.run_test()

    def trigger_run_test(self):
        if self._is_highlighting: return
        self.debounce_timer.start()

    def run_test(self):
        content = self.input_edit.toPlainText()
        if not content:
            self.result_model.set_data([])
            self.lbl_stats.setText("")
            self.highlighter.set_matches([])
            return

        start_time = time.perf_counter()

        active_rules = []
        if self.rb_all.isChecked():
            active_rules = [r for r in self.rules if r.get("enabled", True)]
        else:
            current_id = self.combo_rules.currentData()
            rule = next((r for r in self.rules if r["id"] == current_id), None)
            if rule:
                active_rules = [rule]

        all_matches = []
        MAX_MATCHES = 10000
        limit_reached = False

        for rule in active_rules:
            if limit_reached: break

            left = rule.get("left_delimiter", "")
            right = rule.get("right_delimiter", "")
            is_multiline = rule.get("multiline", True)

            if not left or not right: continue

            try:
                flags = re.DOTALL if is_multiline else 0
                full_regex = f"({left})(.*?)({right})"
                pattern = re.compile(full_regex, flags)

                for m in pattern.finditer(content):
                    if len(all_matches) >= MAX_MATCHES:
                        limit_reached = True
                        break

                    raw_content = m.group(2)
                    full_start = m.start()
                    full_end = m.end()

                    all_matches.append({
                        'rule_name': rule.get("name", "Unknown"),
                        'raw': raw_content,
                        'processed': unescape_overwatch_string(raw_content),
                        'start': full_start,
                        'end': full_end,
                        'content_start': m.start(2),
                        'content_end': m.end(2),
                        'is_conflict': False
                    })
            except re.error:
                pass

        all_matches.sort(key=lambda x: x['start'])

        last_end = -1
        conflict_count = 0
        for m in all_matches:
            if m['start'] < last_end:
                m['is_conflict'] = True
                conflict_count += 1
            if m['end'] > last_end:
                last_end = m['end']

        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000

        self.result_model.set_data(all_matches)

        highlight_data = []
        HIGHLIGHT_LIMIT = 1000

        if len(all_matches) <= HIGHLIGHT_LIMIT:
            for m in all_matches:
                highlight_data.append({
                    'start': m['content_start'],
                    'end': m['content_end'],
                    'is_conflict': m['is_conflict']
                })

        status_msg = _("Found {count} matches in {time:.1f}ms. Conflicts: {conflicts}").format(
            count=len(all_matches), time=duration_ms, conflicts=conflict_count
        )
        if limit_reached:
            status_msg += f" ({_('Limit reached')})"
        if len(all_matches) > HIGHLIGHT_LIMIT:
            status_msg += f" - {_('Highlighting disabled')}"

        self.lbl_stats.setText(status_msg)

        self._is_highlighting = True
        self.highlighter.set_matches(highlight_data)
        self._is_highlighting = False

    def _on_table_item_clicked(self, index):
        if not index.isValid(): return

        # Get data from model directly
        match_data = self.result_model.data(index, Qt.UserRole)

        if match_data:
            cursor = self.input_edit.textCursor()
            cursor.setPosition(match_data['content_start'])
            cursor.setPosition(match_data['content_end'], QTextCursor.KeepAnchor)
            self.input_edit.setTextCursor(cursor)
            self.input_edit.setFocus()

    def export_results(self):
        filepath, __ = QFileDialog.getSaveFileName(
            self, _("Export Test Results"), "extraction_results.json", "JSON Files (*.json)"
        )
        if not filepath: return

        results = []
        for m in self.result_model._data:
            clean_data = {k: v for k, v in m.items() if k != 'is_conflict'}
            results.append(clean_data)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, _("Success"), _("Results exported successfully."))
        except Exception as e:
            QMessageBox.critical(self, _("Error"), str(e))


# --- 规则管理器 ---
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

        test_all_btn = QPushButton(_("Test Rules..."))
        test_all_btn.clicked.connect(self.test_all_rules)
        toolbar.addWidget(test_all_btn)

        toolbar.addStretch(1)

        import_btn = QPushButton(_("Import Preset"))
        import_btn.clicked.connect(self.import_preset)
        toolbar.addWidget(import_btn)

        export_btn = QPushButton(_("Export Preset"))
        export_btn.clicked.connect(self.export_preset)
        toolbar.addWidget(export_btn)

        reset_btn = QPushButton(_("Reset Defaults"))
        reset_btn.clicked.connect(self.reset_to_defaults)
        toolbar.addWidget(reset_btn)

        main_layout.addLayout(toolbar)

        # Tree View
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([_("Enabled"), _("Rule Name"), _("Category"), _("Left Delimiter"), _("Right Delimiter")])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tree.setSelectionBehavior(QTreeWidget.SelectRows)
        self.tree.setDragDropMode(QTreeWidget.InternalMove)
        self.tree.itemDoubleClicked.connect(self.edit_item)

        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)

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
            if not pattern.get("enabled", True):
                for i in range(5):
                    item.setForeground(i, QColor("gray"))
            self.tree.addTopLevelItem(item)

    def show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return

        menu = QMenu(self)
        edit_action = QAction(_("Edit"), self)
        edit_action.triggered.connect(lambda: self.edit_item(item, 0))
        menu.addAction(edit_action)

        test_action = QAction(_("Test This Rule"), self)
        test_action.triggered.connect(lambda: self.test_single_rule_from_list(item))
        menu.addAction(test_action)

        menu.addSeparator()

        toggle_action = QAction(_("Toggle Enable/Disable"), self)
        toggle_action.triggered.connect(lambda: self.toggle_item(item))
        menu.addAction(toggle_action)

        delete_action = QAction(_("Delete"), self)
        delete_action.triggered.connect(self.delete_item)
        menu.addAction(delete_action)

        menu.exec(self.tree.mapToGlobal(pos))

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

        dialog = ExtractionPatternItemEditor(self, _("Add Extraction Rule"), new_pattern, self.patterns_buffer)
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

        reply = QMessageBox.question(self, _("Confirm Delete"), _("Are you sure you want to delete the selected rule?"),
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No: return

        selected_id = selected_items[0].data(0, Qt.UserRole)
        self.patterns_buffer = [p for p in self.patterns_buffer if p["id"] != selected_id]
        self.populate_tree()

    def toggle_item(self, item):
        item_id = item.data(0, Qt.UserRole)
        for p in self.patterns_buffer:
            if p["id"] == item_id:
                p["enabled"] = not p.get("enabled", True)
                break
        self.populate_tree()

    def edit_item(self, item, column):
        item_id = item.data(0, Qt.UserRole)
        pattern_to_edit = next((p for p in self.patterns_buffer if p["id"] == item_id), None)
        if not pattern_to_edit:
            return

        dialog = ExtractionPatternItemEditor(self, _("Edit Extraction Rule"), pattern_to_edit, self.patterns_buffer)
        if dialog.exec():
            for i, p_item in enumerate(self.patterns_buffer):
                if p_item["id"] == item_id:
                    self.patterns_buffer[i] = dialog.result
                    break
            self.populate_tree()

    def test_all_rules(self):
        self.get_current_order_from_tree()
        dialog = ExtractionPatternTestDialog(self, self.patterns_buffer, initial_rule_id=None)
        dialog.exec()

    def test_single_rule_from_list(self, item):
        item_id = item.data(0, Qt.UserRole)
        self.get_current_order_from_tree()
        dialog = ExtractionPatternTestDialog(self, self.patterns_buffer, initial_rule_id=item_id)
        dialog.exec()

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
            self.get_current_order_from_tree()
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


# --- 规则编辑器 ---
class ExtractionPatternItemEditor(QDialog):
    def __init__(self, parent, title, initial_data, all_rules_ref=None):
        super().__init__(parent)
        self.initial_data = initial_data
        self.all_rules_ref = all_rules_ref
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

        # Category
        string_type_layout = QHBoxLayout()
        string_type_layout.addWidget(QLabel(_("Category:")))
        self.string_type_entry = QLineEdit(self.initial_data.get("string_type", "General"))
        self.string_type_entry.setPlaceholderText(_("e.g. UI, Dialogue, System, UI"))
        string_type_layout.addWidget(self.string_type_entry)
        main_layout.addLayout(string_type_layout)

        # Generated Comment
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel(_("Comment:")))
        self.desc_entry = QLineEdit(self.initial_data.get("description", ""))
        self.desc_entry.setPlaceholderText(_("Comment shown to translators (e.g. 'Player Name')"))
        desc_layout.addWidget(self.desc_entry)
        main_layout.addLayout(desc_layout)

        # Left Delimiter
        main_layout.addWidget(QLabel(_("Left Delimiter (Regex):")))
        self.left_text_edit = QPlainTextEdit(self.initial_data.get("left_delimiter", ""))
        self.left_text_edit.setFixedHeight(60)
        main_layout.addWidget(self.left_text_edit)

        # Right Delimiter
        main_layout.addWidget(QLabel(_("Right Delimiter (Regex):")))
        self.right_text_edit = QPlainTextEdit(self.initial_data.get("right_delimiter", ""))
        self.right_text_edit.setFixedHeight(60)
        main_layout.addWidget(self.right_text_edit)

        # Options
        options_layout = QHBoxLayout()
        self.multiline_checkbox = QCheckBox(_("Dot Matches Newline (DOTALL)"))
        self.multiline_checkbox.setChecked(self.initial_data.get("multiline", True))
        self.multiline_checkbox.setToolTip(
            _("If unchecked, extraction will stop at the end of the line. Useful for INI files."))
        options_layout.addWidget(self.multiline_checkbox)
        options_layout.addStretch()
        main_layout.addLayout(options_layout)

        # Regex Escape Buttons
        button_frame = QHBoxLayout()
        escape_left_btn = QPushButton(_("Escape Special Chars (Left)"))
        escape_left_btn.setToolTip(_("Automatically escape characters like ( ) [ ] . * ? for literal matching."))
        escape_left_btn.clicked.connect(lambda: self.convert_to_regex('left'))
        button_frame.addWidget(escape_left_btn)

        escape_right_btn = QPushButton(_("Escape Special Chars (Right)"))
        escape_right_btn.setToolTip(_("Automatically escape characters like ( ) [ ] . * ? for literal matching."))
        escape_right_btn.clicked.connect(lambda: self.convert_to_regex('right'))
        button_frame.addWidget(escape_right_btn)

        ai_btn = QPushButton(_("✨ AI Generate"))
        ai_btn.setToolTip(_("Let AI analyze your text and generate regex for you."))
        ai_btn.clicked.connect(self.open_ai_generator)
        button_frame.addWidget(ai_btn)

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

    def get_current_rule_state(self):
        """Constructs a rule dict from current UI state"""
        return {
            "id": self.initial_data["id"],
            "name": self.name_entry.text().strip() or "Unnamed",
            "enabled": self.enabled_checkbox.isChecked(),
            "string_type": self.string_type_entry.text().strip(),
            "description": self.desc_entry.text().strip(),
            "left_delimiter": self.left_text_edit.toPlainText().strip(),
            "right_delimiter": self.right_text_edit.toPlainText().strip(),
            "multiline": self.multiline_checkbox.isChecked()
        }

    def open_ai_generator(self):
        dialog = AIRegexGeneratorDialog(self, self.parent().app) # Need app instance for AI
        if dialog.exec():
            data = dialog.result
            if data:
                self.left_text_edit.setPlainText(data["left"])
                self.right_text_edit.setPlainText(data["right"])
                self.multiline_checkbox.setChecked(data["multiline"])

    def open_tester(self):
        current_rule = self.get_current_rule_state()

        rules_to_pass = []
        if self.all_rules_ref:
            rules_to_pass = deepcopy(self.all_rules_ref)
            found = False
            for i, r in enumerate(rules_to_pass):
                if r["id"] == current_rule["id"]:
                    rules_to_pass[i] = current_rule
                    found = True
                    break
            if not found:
                rules_to_pass.append(current_rule)
        else:
            rules_to_pass = [current_rule]

        dialog = ExtractionPatternTestDialog(
            self,
            rules_to_pass,
            initial_rule_id=current_rule["id"]
        )
        dialog.exec()

    def accept(self):
        name = self.name_entry.text().strip()
        left_delimiter = self.left_text_edit.toPlainText().strip()
        right_delimiter = self.right_text_edit.toPlainText().strip()

        if not name:
            QMessageBox.critical(self, _("Error"), _("Rule name cannot be empty."))
            return
        if not left_delimiter or not right_delimiter:
            QMessageBox.critical(self, _("Error"), _("Left and right delimiters cannot be empty."))
            return

        self.result = self.get_current_rule_state()
        super().accept()

    def reject(self):
        self.result = None
        super().reject()