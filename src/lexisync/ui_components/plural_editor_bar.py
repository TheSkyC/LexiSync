# Copyright (c) 2025-2026, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QEasingCurve, QEvent, QParallelAnimationGroup, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QCursor, QIcon, QPainter
from PySide6.QtWidgets import QButtonGroup, QComboBox, QHBoxLayout, QPushButton, QStyle, QStyledItemDelegate, QWidget

from lexisync.ui_components.tooltip import Tooltip
from lexisync.utils.localization import _
from lexisync.utils.path_utils import get_resource_path


class _PluralFlatButton(QPushButton):
    def __init__(self, category, examples, parent_bar):
        super().__init__(category, parent_bar)
        self.category = category
        self.examples = examples
        self.parent_bar = parent_bar
        self.setProperty("flat_btn", "true")
        self.setCheckable(True)
        self.setFixedHeight(28)
        self.setCursor(Qt.PointingHandCursor)

        self.setToolTip("")

    def event(self, event):
        if event.type() == QEvent.Enter:
            title_color = "#409EFF" if self.isChecked() else "#FFFFFF"
            html = (
                f"<b style='color:{title_color}; font-size:12px;'>{self.category}</b>"
                f"<hr style='border-color: #666; margin: 4px 0;'>"
                f"<div style='font-family:Consolas; color:#DDD;'>n → {self.examples}</div>"
            )
            self.parent_bar.tooltip.show_tooltip(QCursor.pos(), html, delay=300)
            return True

        if event.type() == QEvent.Leave or event.type() == QEvent.MouseButtonPress:
            self.parent_bar.tooltip.hide()

        return super().event(event)


class PluralComboBoxDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index):
        painter.save()

        # 1. 绘制背景 (处理选中/悬停状态)
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.fillRect(option.rect, option.palette.base())
            painter.setPen(option.palette.text().color())

        # 2. 获取数据：DisplayRole 是主标题，UserRole 是示例文字
        title = index.data(Qt.DisplayRole)
        example = index.data(Qt.UserRole)

        # 3. 计算上下两行的绘制区域
        rect = option.rect
        title_rect = rect.adjusted(8, 4, -8, -rect.height() // 2 + 2)
        ex_rect = rect.adjusted(8, rect.height() // 2, -8, -4)

        # 4. 绘制主标题 (加粗)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignBottom, title)

        # 5. 绘制副标题 (小字、灰色)
        font.setBold(False)
        font.setPointSize(max(8, font.pointSize() - 1))
        painter.setFont(font)
        if not (option.state & QStyle.State_Selected):
            painter.setPen(Qt.gray)
        painter.drawText(ex_rect, Qt.AlignLeft | Qt.AlignTop, f"n → {example}")

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(140, 38)


class PluralEditorBar(QWidget):
    index_changed = Signal(int)
    mode_toggled = Signal(bool)  # True=Compact, False=Flat

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plural_info = []
        self.current_index = 0
        self.is_compact_mode = False

        self.tooltip = Tooltip(self)

        self.setFixedHeight(28)

        icon_down = get_resource_path("icons/chevron-down.svg").replace("\\", "/")
        self.setStyleSheet(f"""
            PluralEditorBar {{
                background-color: #F8F9FA;
                border-bottom: 1px solid #E0E0E0;
            }}
            /* 平铺按钮基础样式 */
            QPushButton[flat_btn="true"] {{
                background-color: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 0px 10px;
                color: #555;
                font-weight: bold;
            }}
            /* 平铺按钮悬停 */
            QPushButton[flat_btn="true"]:hover {{
                color: #000;
                background-color: #EAECEF;
            }}
            /* 平铺按钮选中状态 (蓝色下划线) */
            QPushButton[flat_btn="true"]:checked {{
                color: #0D6EFD;
                border-bottom: 2px solid #0D6EFD;
            }}
            /* 组合框样式 */
            QComboBox {{
                background-color: #FFFFFF;
                border: 1px solid #DCDFE6;
                border-radius: 3px;
                padding: 0px 8px;
                color: #333;
                font-weight: bold;
                min-height: 22px;
                max-height: 22px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #DCDFE6;
                background-color: #FAFAFA;
            }}
            QComboBox::down-arrow {{
                image: url("{icon_down}");
                width: 10px;
                height: 10px;
            }}
            QComboBox::drop-down:hover {{
                background-color: #F0F2F5;
            }}
            /* 切换按钮样式 */
            QPushButton#toggleBtn {{
                background-color: transparent;
                border: none;
                padding: 2px;
                border-radius: 3px;
            }}
            QPushButton#compactBtn:hover {{
                border-color: #409EFF;
            }}
        """)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 5, 0)
        self.layout.setSpacing(4)

        # 1. 平铺容器
        self.flat_container = QWidget()
        self.flat_layout = QHBoxLayout(self.flat_container)
        self.flat_layout.setContentsMargins(0, 0, 0, 0)
        self.flat_layout.setSpacing(0)
        self.btn_group = QButtonGroup(self)
        self.btn_group.buttonClicked.connect(self._on_flat_btn_clicked)

        # 2. 紧凑模式组合框 (替换原有的 QPushButton + QMenu)
        self.compact_combo = QComboBox()
        self.compact_combo.setItemDelegate(PluralComboBoxDelegate(self.compact_combo))
        self.compact_combo.currentIndexChanged.connect(self._on_combo_changed)
        self.compact_combo.hide()

        # 3. 切换按钮
        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("toggleBtn")
        self.toggle_btn.setFixedSize(22, 22)
        self.toggle_btn.setIcon(QIcon(get_resource_path("icons/list.svg")))
        self.toggle_btn.setToolTip(_("Switch to list view"))
        self.toggle_btn.clicked.connect(self._toggle_mode)

        self.layout.addWidget(self.flat_container)
        self.layout.addWidget(self.compact_combo)
        self.layout.addWidget(self.toggle_btn)
        self.layout.addStretch()

    def setup_plurals(self, plural_info, saved_mode=False):
        """
        配置复数表单。
        """
        self.setUpdatesEnabled(False)

        try:
            self.plural_info = plural_info
            self.is_compact_mode = saved_mode
            self.current_index = 0

            while self.flat_layout.count():
                item = self.flat_layout.takeAt(0)
                if item.widget():
                    item.widget().hide()
                    item.widget().deleteLater()

            # 清理按钮组
            for btn in self.btn_group.buttons():
                self.btn_group.removeButton(btn)

            # 清理组合框
            self.compact_combo.blockSignals(True)
            self.compact_combo.clear()

            for info in plural_info:
                idx = info["index"]
                cat = info["category"]
                ex = info["examples"]

                # Flat Button
                btn = _PluralFlatButton(cat, ex, self)
                self.btn_group.addButton(btn, id=idx)
                self.flat_layout.addWidget(btn)

                # Compact ComboBox Item
                self.compact_combo.addItem(f"Index {idx}: {cat}", userData=ex)
                self.compact_combo.setItemData(self.compact_combo.count() - 1, idx, Qt.UserRole + 1)

            self.compact_combo.blockSignals(False)

            # 默认选中
            if self.btn_group.button(0):
                self.btn_group.button(0).setChecked(True)

            if self.is_compact_mode:
                self.flat_container.hide()
                self.compact_combo.show()
                self.toggle_btn.setIcon(QIcon(get_resource_path("icons/grid.svg")))
                self.toggle_btn.setToolTip(_("Switch to grid view"))
                self._sync_combo_index(0)
            else:
                self.compact_combo.hide()
                self.flat_container.show()
                self.toggle_btn.setIcon(QIcon(get_resource_path("icons/list.svg")))
                self.toggle_btn.setToolTip(_("Switch to list view"))

        finally:
            self.setUpdatesEnabled(True)
            self.update()

    def _on_flat_btn_clicked(self, btn):
        idx = self.btn_group.id(btn)
        if idx != self.current_index:
            self.current_index = idx
            # 同步 ComboBox 的状态
            self._sync_combo_index(idx)
            self.index_changed.emit(idx)

    def _on_combo_changed(self, combo_idx):
        if combo_idx >= 0:
            # 提取真实的 idx
            actual_idx = self.compact_combo.itemData(combo_idx, Qt.UserRole + 1)
            if actual_idx != self.current_index:
                self.current_index = actual_idx
                # 同步 Flat Button 的状态
                if self.btn_group.button(actual_idx):
                    self.btn_group.button(actual_idx).setChecked(True)
                self.index_changed.emit(actual_idx)

    def _sync_combo_index(self, target_idx):
        """辅助方法：根据真实的 idx 寻找 ComboBox 中的位置并选中"""
        self.compact_combo.blockSignals(True)
        for i in range(self.compact_combo.count()):
            if self.compact_combo.itemData(i, Qt.UserRole + 1) == target_idx:
                self.compact_combo.setCurrentIndex(i)
                break
        self.compact_combo.blockSignals(False)

    def _toggle_mode(self):
        self.is_compact_mode = not self.is_compact_mode
        self._animate_transition()
        self.mode_toggled.emit(self.is_compact_mode)

    def _animate_transition(self):
        # 1. 停止正在运行的旧动画，防止快速连点时出现冲突
        if hasattr(self, "anim_group") and self.anim_group.state() == QParallelAnimationGroup.Running:
            self.anim_group.stop()

        self.anim_group = QParallelAnimationGroup(self)

        # 2. 针对两个容器的 maximumWidth 属性创建动画
        anim_flat = QPropertyAnimation(self.flat_container, b"maximumWidth")
        anim_compact = QPropertyAnimation(self.compact_combo, b"maximumWidth")

        # 设定动画时长 (250毫秒) 和 缓动曲线
        duration = 250
        easing = QEasingCurve.InOutQuad

        anim_flat.setDuration(duration)
        anim_flat.setEasingCurve(easing)
        anim_compact.setDuration(duration)
        anim_compact.setEasingCurve(easing)

        if self.is_compact_mode:
            # 【切换到紧凑模式 (下拉框)】
            self.compact_combo.setMaximumWidth(0)  # 先压扁
            self.compact_combo.show()  # 强行显示出来占位

            # 扁平按钮容器：从当前宽度 -> 缩小到 0
            anim_flat.setStartValue(self.flat_container.width())
            anim_flat.setEndValue(0)

            # 下拉框：从 0 -> 放大到最佳提示宽度
            target_width = self.compact_combo.sizeHint().width()
            anim_compact.setStartValue(0)
            anim_compact.setEndValue(target_width)

            # 绑定动画结束的清理动作
            self.anim_group.finished.connect(self._on_anim_to_compact_finished)
        else:
            # 【切换到扁平模式 (平铺按钮)】
            self.flat_container.setMaximumWidth(0)
            self.flat_container.show()

            anim_compact.setStartValue(self.compact_combo.width())
            anim_compact.setEndValue(0)

            target_width = self.flat_container.sizeHint().width()
            anim_flat.setStartValue(0)
            anim_flat.setEndValue(target_width)

            self.anim_group.finished.connect(self._on_anim_to_flat_finished)

        # 3. 将两个动画加入组并同时启动
        self.anim_group.addAnimation(anim_flat)
        self.anim_group.addAnimation(anim_compact)
        self.anim_group.start()

    def _on_anim_to_compact_finished(self):
        """动画结束后的清理工作"""
        self.flat_container.hide()
        self.compact_combo.setMaximumWidth(16777215)  # 恢复 Qt 默认的无限制宽度
        self.toggle_btn.setIcon(QIcon(get_resource_path("icons/grid.svg")))
        self.toggle_btn.setToolTip(_("Switch to grid view"))
        self._sync_combo_index(self.current_index)
        self.anim_group.finished.disconnect(self._on_anim_to_compact_finished)

    def _on_anim_to_flat_finished(self):
        self.compact_combo.hide()
        self.flat_container.setMaximumWidth(16777215)
        self.toggle_btn.setIcon(QIcon(get_resource_path("icons/list.svg")))
        self.toggle_btn.setToolTip(_("Switch to list view"))
        if self.btn_group.button(self.current_index):
            self.btn_group.button(self.current_index).setChecked(True)

        self.anim_group.finished.disconnect(self._on_anim_to_flat_finished)

    def _update_visibility(self):
        if self.is_compact_mode:
            self.flat_container.hide()
            self.compact_combo.show()
            self.toggle_btn.setIcon(QIcon(get_resource_path("icons/grid.svg")))
            self.toggle_btn.setToolTip(_("Switch to grid view"))
            self._sync_combo_index(self.current_index)
        else:
            self.flat_container.show()
            self.compact_combo.hide()
            self.toggle_btn.setIcon(QIcon(get_resource_path("icons/list.svg")))
            self.toggle_btn.setToolTip(_("Switch to list view"))
            if self.btn_group.button(self.current_index):
                self.btn_group.button(self.current_index).setChecked(True)
