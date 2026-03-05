# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeView,
    QHeaderView, QFrame, QTextEdit, QStyledItemDelegate
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import (QStandardItemModel, QStandardItem, QColor,
                           QFont, QIcon, QPainter, QBrush)
from utils.localization import _
import difflib


class DiffDialog(QDialog):
    def __init__(self, parent, title, diff_results):
        super().__init__(parent)
        self.diff_results = diff_results
        self.decisions = {}  # 存储最终决策结果

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(1100, 750)

        self.setup_ui()
        self.populate_tree()

        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
            }
            QTreeView {
                border: none;
                background-color: #FFFFFF;
                outline: 0;
                color: #333333; /* 显式设置默认文字颜色 */
            }
            QTreeView::item {
                min-height: 30px; /* 用高度代替 padding */
                border-radius: 4px;
            }
            QTreeView::item:selected {
                background-color: #E3F2FD;
                color: #000000;
            }
            QTreeView::item:hover:!selected {
                background-color: #F5F5F5;
            }
            QHeaderView::section {
                background-color: #FFFFFF;
                padding: 4px;
                border: none;
                border-bottom: 1px solid #EEEEEE;
                font-weight: bold;
                color: #555555;
            }
            QTextEdit {
                border: 1px solid #EEEEEE;
                border-radius: 6px;
                background-color: #FAFAFA;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
        """)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # 顶部说明
        summary_text = self.diff_results.get('summary', _('Comparison Results'))
        summary_label = QLabel(summary_text)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("font-size: 14px; color: #333; font-weight: bold;")
        main_layout.addWidget(summary_label)

        # 提示语
        hint_label = QLabel(
            _("Uncheck items to reject changes. Rejected 'Modified' items will be split into 'Delete Old' + 'Add New'."))
        hint_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 5px;")
        main_layout.addWidget(hint_label)

        # 主内容区
        content_layout = QHBoxLayout()

        # 左侧树
        self.tree = QTreeView()
        self.tree.setAlternatingRowColors(False)
        self.tree.setHeaderHidden(False)
        self.tree.setEditTriggers(QTreeView.NoEditTriggers)
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels([_("Change"), _("Detail")])
        self.tree.setModel(self.model)

        # 联动复选框
        self.model.itemChanged.connect(self.on_item_changed)
        self.tree.selectionModel().selectionChanged.connect(self.on_selection_changed)

        content_layout.addWidget(self.tree, 2)

        # 右侧详情
        right_panel = QVBoxLayout()
        right_panel.setContentsMargins(0, 0, 0, 0)
        right_panel.addWidget(QLabel(_("Diff Preview")))

        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFont(QFont("Consolas", 10))
        right_panel.addWidget(self.diff_view)

        content_layout.addLayout(right_panel, 1)
        main_layout.addLayout(content_layout)

        # 底部按钮
        btn_layout = QHBoxLayout()

        self.btn_confirm = QPushButton(_("Apply Selected Changes"))
        self.btn_confirm.setStyleSheet("background-color: #4CAF50; color: white; border: none;")
        self.btn_confirm.clicked.connect(self.accept)

        self.btn_cancel = QPushButton(_("Cancel"))
        self.btn_cancel.setStyleSheet("background-color: #F5F5F5; border: 1px solid #DDD; color: #333;")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_confirm)
        main_layout.addLayout(btn_layout)

    def populate_tree(self):
        # 1. 新增 (Added)
        self._add_category_node(
            _("Added"),
            self.diff_results.get('added', []),
            QColor("#4CAF50"),
            "new_obj",
            is_checkable=True
        )

        # 2. 修改 (Modified)
        self._add_category_node(
            _("Modified"),
            self.diff_results.get('modified', []),
            QColor("#FF9800"),
            "new_obj",
            is_checkable=True,
            show_similarity=True
        )

        # 3. 删除 (Removed)
        self._add_category_node(
            _("Removed"),
            self.diff_results.get('removed', []),
            QColor("#F44336"),
            "old_obj",
            is_checkable=True
        )

        # 4. 未变动 (Unchanged)
        self._add_category_node(
            _("Unchanged"),
            self.diff_results.get('unchanged', []),
            QColor("#9E9E9E"),
            "new_obj",
            is_checkable=False,  # 不可取消勾选，作为基准
            default_expanded=False
        )

        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)

    def _add_category_node(self, title, items, color, obj_key, is_checkable=True, show_similarity=False,
                           default_expanded=True):
        if not items: return

        # 显式创建 Item
        root_item = QStandardItem(str(title) + f" ({len(items)})")
        root_item.setForeground(QBrush(color))
        font = QFont()
        font.setBold(True)
        root_item.setFont(font)

        if is_checkable:
            root_item.setCheckable(True)
            root_item.setCheckState(Qt.Checked)
            root_item.setData("root", Qt.UserRole + 1)

        for item_data in items:
            ts_obj = item_data[obj_key]
            text = str(ts_obj.original_semantic).replace('\n', ' ')
            if len(text) > 80: text = text[:77] + "..."

            child_item = QStandardItem(text)
            child_item.setData(item_data, Qt.UserRole)

            if is_checkable:
                child_item.setCheckable(True)
                child_item.setCheckState(Qt.Checked)

            detail_text = ""
            if show_similarity:
                sim = item_data.get('similarity', 0)
                detail_text = f"{sim:.0%} similarity"

            detail_item = QStandardItem(detail_text)
            detail_item.setForeground(QBrush(QColor("#888888")))

            root_item.appendRow([child_item, detail_item])

        self.model.appendRow([root_item, QStandardItem("")])
        if default_expanded:
            self.tree.expand(self.model.indexFromItem(root_item))

    def on_item_changed(self, item):
        """处理复选框联动逻辑"""
        if item.isCheckable():
            state = item.checkState()

            # 如果是根节点，全选/全不选子节点
            if item.data(Qt.UserRole + 1) == "root":
                for i in range(item.rowCount()):
                    child = item.child(i)
                    if child.checkState() != state:
                        child.setCheckState(state)

            # 如果是子节点，更新根节点状态
            elif item.parent():
                parent = item.parent()
                checked_count = 0
                for i in range(parent.rowCount()):
                    if parent.child(i).checkState() == Qt.Checked:
                        checked_count += 1

                if checked_count == parent.rowCount():
                    new_state = Qt.Checked
                elif checked_count == 0:
                    new_state = Qt.Unchecked
                else:
                    new_state = Qt.PartiallyChecked

                if parent.checkState() != new_state:
                    # 阻止父节点变更再次触发子节点更新
                    self.model.blockSignals(True)
                    parent.setCheckState(new_state)
                    self.model.blockSignals(False)

    def on_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if not indexes:
            self.diff_view.clear()
            return

        # 只处理第一列
        index = indexes[0]
        if index.column() != 0:
            index = index.siblingAtColumn(0)

        item = self.model.itemFromIndex(index)
        item_data = item.data(Qt.UserRole)

        if not item_data:
            self.diff_view.clear()
            return

        if 'old_obj' in item_data and 'new_obj' in item_data:  # Modified
            old_text = item_data['old_obj'].original_semantic
            new_text = item_data['new_obj'].original_semantic
            self._display_inline_diff(old_text, new_text)
        elif 'new_obj' in item_data:  # Added / Unchanged
            self.diff_view.setHtml(
                f"<div style='color:#4CAF50; font-weight:bold;'>{_('New Content')}:</div>"
                f"<div style='margin-top:5px;'>{self._escape(item_data['new_obj'].original_semantic)}</div>"
            )
        elif 'old_obj' in item_data:  # Removed
            self.diff_view.setHtml(
                f"<div style='color:#F44336; font-weight:bold;'>{_('Removed Content')}:</div>"
                f"<div style='margin-top:5px; text-decoration:line-through; color:#888;'>"
                f"{self._escape(item_data['old_obj'].original_semantic)}</div>"
            )

    def _display_inline_diff(self, old_text, new_text):
        diff = difflib.ndiff(old_text.split(), new_text.split())
        html = []
        for line in diff:
            code = line[:2]
            text = self._escape(line[2:])
            if code == '+ ':
                html.append(f"<span style='background:#E8F5E9; color:#2E7D32;'>{text}</span>")
            elif code == '- ':
                html.append(
                    f"<span style='background:#FFEBEE; color:#C62828; text-decoration:line-through;'>{text}</span>")
            elif code == '? ':
                continue
            else:
                html.append(text)
        self.diff_view.setHtml(" ".join(html))

    def _escape(self, text):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

    def get_decisions(self):
        """
        根据用户勾选状态，生成最终的决策清单。
        """
        decisions = {
            'added': [],
            'removed': [],
            'modified': [],
            'unchanged': []  # 始终包含
        }

        # 1. 处理 Unchanged (始终保留)
        decisions['unchanged'] = [item['new_obj'] for item in self.diff_results.get('unchanged', [])]

        # 2. 遍历树节点获取决策
        root = self.model.invisibleRootItem()
        for i in range(root.rowCount()):
            category_item = root.child(i)
            title = category_item.text()

            # 跳过 Unchanged 组
            if "Unchanged" in title: continue

            for j in range(category_item.rowCount()):
                child = category_item.child(j)
                item_data = child.data(Qt.UserRole)
                is_checked = (child.checkState() == Qt.Checked)

                if "Added" in title:
                    if is_checked:
                        decisions['added'].append(item_data['new_obj'])
                    # Unchecked: 丢弃，不加入任何列表

                elif "Removed" in title:
                    if is_checked:
                        # 确认删除，不加入任何列表（即在最终合并时消失）
                        pass
                    else:
                        # 拒绝删除 -> 保留旧对象，并标记废弃
                        old_obj = item_data['old_obj']
                        old_obj.is_ignored = True
                        old_obj.comment = f"[{_('Obsolete')}] {old_obj.comment}".strip()
                        decisions['unchanged'].append(old_obj)

                elif "Modified" in title:
                    if is_checked:
                        # 确认修改 -> 迁移属性
                        old_obj = item_data['old_obj']
                        new_obj = item_data['new_obj']

                        # 迁移逻辑 (与之前相同)
                        new_obj.set_translation_internal(old_obj.translation)
                        new_obj.comment = old_obj.comment
                        new_obj.is_reviewed = False  # 修改后需重审
                        new_obj.is_fuzzy = True
                        new_obj.po_comment = old_obj.po_comment

                        decisions['modified'].append(new_obj)
                    else:
                        # 拒绝修改 -> 拆解为：保留旧的(废弃) + 新增新的
                        old_obj = item_data['old_obj']
                        old_obj.is_ignored = True
                        old_obj.comment = f"[{_('Obsolete')}] {old_obj.comment}".strip()
                        decisions['unchanged'].append(old_obj)

                        new_obj = item_data['new_obj']
                        decisions['added'].append(new_obj)

        return decisions

    def accept(self):
        self.decisions = self.get_decisions()
        super().accept()