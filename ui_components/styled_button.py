# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QColor, QFont


class StyledButton(QPushButton):

    # Predefined Palettes
    PRESETS = {
        "default": {
            "normal_bg": "#FFFFFF", "normal_border": "#DCDFE6", "normal_text": "#606266",
            "hover_bg": "#ECF5FF", "hover_border": "#C6E2FF", "hover_text": "#409EFF",
            "pressed_bg": "#ECF5FF", "pressed_border": "#3A8EE6", "pressed_text": "#3A8EE6"
        },
        "primary": {"base": "#409EFF"},
        "success": {"base": "#67C23A"},
        "warning": {"base": "#E6A23C"},
        "danger": {"base": "#F56C6C"},
        "info": {"base": "#909399"},
        "purple": {"base": "#9C27B0"},
    }

    def __init__(self, text="", on_click=None,
                 btn_type="default", color=None,
                 icon=None, tooltip=None, parent=None):
        super().__init__(text, parent)

        if on_click:
            self.clicked.connect(on_click)
        if icon:
            self.setIcon(icon)
        if tooltip:
            self.setToolTip(tooltip)

        self.setCursor(Qt.PointingHandCursor)

        # Determine Palette
        if color:
            palette = self.generate_palette(color)
        elif btn_type in self.PRESETS:
            preset = self.PRESETS[btn_type]
            if "base" in preset:
                palette = self.generate_palette(preset["base"])
            else:
                palette = preset
        else:
            palette = self.PRESETS["default"]

        self._apply_css(palette)

    @staticmethod
    def generate_palette(base_hex: str) -> dict:
        """
        Automatically generates a color palette based on a single base color.
        """
        c = QColor(base_hex)

        def mix_white(color, ratio):
            """Mix color with white. ratio 0 = color, 1 = white"""
            r = color.red() * (1 - ratio) + 255 * ratio
            g = color.green() * (1 - ratio) + 255 * ratio
            b = color.blue() * (1 - ratio) + 255 * ratio
            return QColor(int(r), int(g), int(b)).name()

        return {
            "normal_bg": mix_white(c, 0.9),  # 90% White (Very Pale)
            "normal_border": mix_white(c, 0.8),  # 80% White (Pale)
            "normal_text": base_hex,  # Base Color

            "hover_bg": mix_white(c, 0.8),  # 80% White (Slightly darker than normal bg)
            "hover_border": base_hex,  # Base Color
            "hover_text": base_hex,  # Base Color

            "pressed_bg": c.darker(110).name(),  # Darker Base
            "pressed_border": c.darker(110).name(),
            "pressed_text": "#FFFFFF"  # White Text
        }

    def _apply_css(self, c: dict):
        base_css = """
            QPushButton {
                padding: 5px 15px;
                border-radius: 4px;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                font-size: 13px;
                font-weight: 500;
                border-style: solid;
                border-width: 1px;
            }
            QPushButton:disabled {
                background-color: #F5F7FA;
                border-color: #E4E7ED;
                color: #C0C4CC;
            }
        """

        theme_css = f"""
            QPushButton {{
                background-color: {c['normal_bg']};
                border-color: {c['normal_border']};
                color: {c['normal_text']};
            }}
            QPushButton:hover {{
                background-color: {c['hover_bg']};
                border-color: {c['hover_border']};
                color: {c['hover_text']};
            }}
            QPushButton:pressed {{
                background-color: {c['pressed_bg']};
                border-color: {c['pressed_border']};
                color: {c['pressed_text']};
            }}
        """
        self.setStyleSheet(base_css + theme_css)