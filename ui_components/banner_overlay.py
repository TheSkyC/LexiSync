# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QEvent, QSize, QPoint
from PySide6.QtGui import QIcon, QPixmap, QColor, QFont


class BannerOverlay(QWidget):
    PRESETS = {
        "drop": {
            "bg_color": "rgba(0, 0, 0, 180)", "text_color": "#FFFFFF",
            "border": "none", "border_radius": "15px",
            "font_size": "24px", "font_weight": "bold", "icon_size": 32
        },
        "warning": {
            "bg_color": "rgba(255, 193, 7, 235)", "text_color": "#333333",
            "border": "1px solid #E6A23C", "border_radius": "6px",
            "font_size": "13px", "font_weight": "bold", "icon_size": 16
        },
        "info": {
            "bg_color": "rgba(64, 158, 255, 235)", "text_color": "#FFFFFF",
            "border": "1px solid #3A8EE6", "border_radius": "6px",
            "font_size": "13px", "font_weight": "bold", "icon_size": 16
        },
        "success": {
            "bg_color": "rgba(103, 194, 58, 235)", "text_color": "#FFFFFF",
            "border": "1px solid #5DAF34", "border_radius": "6px",
            "font_size": "13px", "font_weight": "bold", "icon_size": 16
        }
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_StyledBackground, True)


        self._target_widget = parent
        self._layout_mode = "fill"  # 'fill', 'top', 'bottom', 'center'
        self._margin = 0
        self._fixed_height = None

        # 动画设置
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.finished.connect(self._on_anim_finished)

        # UI 布局
        self.main_layout = QHBoxLayout(self)

        self.main_layout.setContentsMargins(10, 5, 10, 5)
        self.main_layout.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.hide()

        self.text_label = QLabel()
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setWordWrap(True)

        self.main_layout.addWidget(self.icon_label)
        self.main_layout.addWidget(self.text_label)

        self.hide()
        if self._target_widget:
            self._target_widget.installEventFilter(self)

    def set_target(self, widget):
        """更改绑定的目标组件"""
        if self._target_widget:
            self._target_widget.removeEventFilter(self)
        self._target_widget = widget
        self.setParent(widget)
        if self._target_widget:
            self._target_widget.installEventFilter(self)
            self._update_geometry()

    def eventFilter(self, obj, event):
        """监听父组件的大小变化，自动调整自身位置和大小"""
        if obj == self._target_widget and event.type() == QEvent.Resize:
            self._update_geometry()
        return super().eventFilter(obj, event)

    def _update_geometry(self):
        if not self._target_widget: return

        tw = self._target_widget.width()
        th = self._target_widget.height()
        m = self._margin

        if self._layout_mode == "fill":
            self.setGeometry(0, 0, tw, th)
        else:
            # 适应内容高度或使用固定高度
            h = self._fixed_height if self._fixed_height else self.sizeHint().height() + 20
            w = tw - (m * 2)

            if self._layout_mode == "bottom":
                self.setGeometry(m, th - h - m, w, h)
            elif self._layout_mode == "top":
                self.setGeometry(m, m, w, h)
            elif self._layout_mode == "center":
                self.setGeometry((tw - w) // 2, (th - h) // 2, w, h)

    def show_message(self, text: str, preset="info", layout_mode="fill", margin=10, fixed_height=None,
                     **custom_styles):
        """
        显示横幅。
        :param text: 显示的文本
        :param preset: 预设样式 ('drop', 'warning', 'info', 'success')
        :param layout_mode: 'fill' (填满), 'top', 'bottom', 'center'
        :param margin: 边缘边距 (仅在非 fill 模式下生效)
        :param fixed_height: 强制指定高度
        :param custom_styles: 覆盖预设的样式 (如 bg_color, text_color 等)
        """
        self._layout_mode = layout_mode
        self._margin = margin
        self._fixed_height = fixed_height

        # 合并样式
        style = self.PRESETS.get(preset, self.PRESETS["info"]).copy()
        style.update(custom_styles)

        # 应用样式
        self.setStyleSheet(f"""
            BannerOverlay {{
                background-color: {style['bg_color']};
                border: {style['border']};
                border-radius: {style['border_radius']};
            }}
        """)

        self.text_label.setStyleSheet(f"""
            QLabel {{
                color: {style['text_color']};
                font-size: {style['font_size']};
                font-weight: {style['font_weight']};
                background: transparent;
                border: none;
            }}
        """)

        self.text_label.setText(text)

        self._update_geometry()

        # 动画显示
        self.show()
        self.raise_()
        self.anim.stop()
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(1.0)
        self.anim.start()

    def hide_banner(self):
        if not self.isVisible() or self.opacity_effect.opacity() == 0:
            return
        self.anim.stop()
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(0.0)
        self.anim.start()

    def show_over_widget(self, target_widget, text: str, preset="info", icon_path=None, **custom_styles):
        pos = target_widget.mapTo(self.parent(), QPoint(0, 0))
        size = target_widget.size()

        self.setGeometry(pos.x(), pos.y(), size.width(), size.height())

        self.show_message(
            text,
            preset=preset,
            icon_path=icon_path,
            layout_mode="fill",
            **custom_styles
        )

    def _on_anim_finished(self):
        if self.opacity_effect.opacity() == 0.0:
            self.hide()