# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from utils.localization import _


class GlossaryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.glossary_list = QListWidget()
        self.glossary_list.setAlternatingRowColors(True)

        self.glossary_list.setStyleSheet("""
            QListWidget {
                border: none;
            }
            QListWidget::item:selected {
                background-color: #E8E8E8; /* 淡灰色背景 */
                color: black; /* 确保文字颜色是黑色 */
            }
            QListWidget::item:hover {
                background-color: #F0F0F0; /* 悬停时更淡的灰色 */
            }
        """)

        layout.addWidget(self.glossary_list)

    def update_matches(self, matches: list):
        self.glossary_list.clear()
        if not matches:
            item = QListWidgetItem(_("No glossary matches found."))
            item.setForeground(Qt.gray)
            self.glossary_list.addItem(item)
            return

        sorted_matches = sorted(matches, key=lambda m: len(m['source']), reverse=True)

        for match in sorted_matches:
            source_term = match['source']
            translations = match['translations']

            target_str = " / ".join([t['target'] for t in translations])

            item_text = f"({source_term}) → {target_str}"
            item = QListWidgetItem(item_text)

            font = item.font()
            font.setPointSize(10)
            item.setFont(font)
            item.setForeground(QColor("#6A0DAD"))  # 使用紫色，与TM的模糊匹配颜色类似

            tooltip_parts = [f"<b>{_('Source Term')}:</b> {source_term}"]
            tooltip_parts.append(f"<b>{_('Recommended Translation(s)')}:</b>")
            for t in translations:
                if t.get('comment'):
                    tooltip_parts.append(f"- {t['target']} ({t['comment']})")
                else:
                    tooltip_parts.append(f"- {t['target']}")
            item.setToolTip("<br>".join(tooltip_parts))

            self.glossary_list.addItem(item)

    def clear_matches(self):
        self.glossary_list.clear()