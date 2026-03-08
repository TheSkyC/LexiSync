# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from lexisync.utils.localization import _


class ColumnMapperDialog(QDialog):
    def __init__(self, parent, headers, sample_data, guessed_mapping):
        super().__init__(parent)
        self.headers = headers
        self.sample_data = sample_data
        self.mapping = guessed_mapping.copy()  # {'source': idx, 'target': idx, 'key': idx, 'comment': idx}
        self.result_mapping = None
        self.remember_choices = False

        self.setWindowTitle(_("Map Columns for Import"))
        self.resize(800, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        info_label = QLabel(_("Please specify the role of each column. At least a 'Source' column is required."))
        info_label.setStyleSheet("font-size: 13px; color: #555; margin-bottom: 10px;")
        layout.addWidget(info_label)

        self.table = QTableWidget()
        col_count = len(self.headers)
        self.table.setColumnCount(col_count)
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(100)

        # Row 0: Comboboxes, Row 1: Headers, Row 2+: Data
        self.table.setRowCount(len(self.sample_data) + 2)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.combos = []
        roles = [
            ("ignore", _("Ignore")),
            ("source", _("Source")),
            ("target", _("Target (Translation)")),
            ("key", _("Key / ID")),
            ("comment", _("Comment / Context")),
        ]

        # 填充表头和下拉框
        for col_idx, header_text in enumerate(self.headers):
            combo = QComboBox()
            combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            combo.view().setMinimumWidth(150)

            for role_id, role_name in roles:
                combo.addItem(role_name, role_id)

            for role_id, mapped_col in self.mapping.items():
                if mapped_col == col_idx:
                    idx = combo.findData(role_id)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    break

            combo.currentIndexChanged.connect(lambda _, c=combo: self._update_combo_style(c))

            self._update_combo_style(combo)

            self.table.setCellWidget(0, col_idx, combo)
            self.combos.append(combo)

            # 表头文本
            header_item = QTableWidgetItem(str(header_text))
            header_item.setBackground(QColor("#E3F2FD"))
            font = QFont()
            font.setBold(True)
            header_item.setFont(font)
            self.table.setItem(1, col_idx, header_item)

        # 填充样本数据
        for row_idx, row_data in enumerate(self.sample_data):
            for col_idx in range(col_count):
                val = str(row_data[col_idx]) if col_idx < len(row_data) else ""
                if len(val) > 50:
                    val = val[:47] + "..."
                item = QTableWidgetItem(val)
                item.setForeground(QColor("#666666"))
                self.table.setItem(row_idx + 2, col_idx, item)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        # 底部操作区
        bottom_layout = QHBoxLayout()
        self.chk_remember = QCheckBox(_("Remember these column mappings for future files"))
        self.chk_remember.setChecked(True)
        bottom_layout.addWidget(self.chk_remember)

        bottom_layout.addStretch()

        btn_cancel = QPushButton(_("Cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton(_("Import"))
        btn_ok.setStyleSheet("background-color: #409EFF; color: white; font-weight: bold;")
        btn_ok.clicked.connect(self.accept_mapping)

        bottom_layout.addWidget(btn_cancel)
        bottom_layout.addWidget(btn_ok)
        layout.addLayout(bottom_layout)

    def accept_mapping(self):
        new_mapping = {}
        for col_idx, combo in enumerate(self.combos):
            role = combo.currentData()
            if role != "ignore":
                if role in new_mapping:
                    QMessageBox.warning(
                        self, _("Error"), _("Role '{role}' is assigned to multiple columns.").format(role=role)
                    )
                    return
                new_mapping[role] = col_idx

        if "source" not in new_mapping:
            QMessageBox.warning(self, _("Error"), _("You must select a 'Source' column."))
            return

        self.result_mapping = new_mapping
        self.remember_choices = self.chk_remember.isChecked()
        self.accept()

    def _update_combo_style(self, combo):
        role = combo.currentData()

        if role == "ignore":
            # 忽略状态：灰色背景，灰色文字
            bg_color = "#F5F5F5"
            text_color = "#9E9E9E"
            border_color = "#DCDFE6"
            font_weight = "normal"
        else:
            # 激活状态（源、译文、键、注释）：浅绿色背景，深绿色文字
            bg_color = "#E8F5E9"
            text_color = "#2E7D32"
            border_color = "#A5D6A7"
            font_weight = "bold"

        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 2px 5px;
                font-weight: {font_weight};
            }}
            QComboBox::drop-down {{
                border: none;
                background: transparent;
            }}
        """)
