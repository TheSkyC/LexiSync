# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QSizePolicy
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor  # 确保 QTextCursor 已导入
from PySide6.QtCore import Qt
from utils.localization import _


class ContextPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

        # 定义高亮格式 (从 setup_ui 移到这里，以便 set_context 能访问)
        self.highlight_format = QTextCharFormat()
        self.highlight_format.setBackground(QColor("yellow"))
        self.highlight_format.setForeground(QColor("black"))  # 确保高亮背景下的文字清晰

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.context_label = QLabel(_("Context Preview:"))
        self.context_label.setObjectName("context_label")
        layout.addWidget(self.context_label)

        self.context_text_display = QTextEdit()
        self.context_text_display.setReadOnly(True)
        self.context_text_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)  # 修正枚举访问
        self.context_text_display.setFontFamily("Consolas")
        self.context_text_display.setFontPointSize(9)
        self.context_text_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # 修正枚举访问
        layout.addWidget(self.context_text_display)

    def set_context(self, context_lines, current_line_in_context_idx):
        self.context_text_display.clear()

        if not context_lines:
            self.context_text_display.setPlainText("")
            return

        processed_lines = [line.replace('\t', '    ') for line in context_lines]
        full_text = "\n".join(processed_lines)
        self.context_text_display.setPlainText(full_text)

        if 0 <= current_line_in_context_idx < len(context_lines):
            doc = self.context_text_display.document()
            current_block = doc.findBlockByNumber(current_line_in_context_idx)

            if not current_block.isValid():
                return

            # --- 1. 应用背景高亮到整个块 ---
            # 创建一个新的块格式
            block_format = current_block.blockFormat()
            block_format.setBackground(self.highlight_format.background())  # 只设置背景色

            # 为这个块创建一个光标并应用块格式
            cursor = QTextCursor(current_block)
            cursor.setBlockFormat(block_format)

            # --- 2. 滚动到这个块的开头 ---
            # 创建一个新的光标，并将其移动到块的开头
            scroll_target_cursor = QTextCursor(doc)
            scroll_target_cursor.setPosition(current_block.position())

            # 将文本编辑器的光标设置为这个新位置
            self.context_text_display.setTextCursor(scroll_target_cursor)

            # 确保这个新光标位置可见，这将触发滚动
            self.context_text_display.ensureCursorVisible()

    def update_ui_texts(self):
        # 使用 objectName 查找更安全
        label = self.findChild(QLabel, "context_label")
        if label:
            label.setText(_("Context Preview:"))