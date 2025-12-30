# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QColor, QFont


class StyledButton(QPushButton):
    # Predefined Color Palettes
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

    # Size Presets
    SIZE_PRESETS = {
        "small": {
            "padding": "4px 10px",
            "font_size": "12px",
            "border_radius": "3px",
        },
        "medium": {
            "padding": "6px 15px",
            "font_size": "13px",
            "border_radius": "4px",
        },
        "large": {
            "padding": "8px 20px",
            "font_size": "14px",
            "border_radius": "5px",
        }
    }

    def __init__(self, text="", on_click=None,
                 btn_type="default", color=None,
                 size="medium",
                 font_family=None,
                 font_size=None,
                 font_weight=None,
                 icon=None, tooltip=None, parent=None):
        super().__init__(text, parent)

        if on_click:
            self.clicked.connect(on_click)
        if icon:
            self.setIcon(icon)
        if tooltip:
            self.setToolTip(tooltip)

        self.setCursor(Qt.PointingHandCursor)

        # Determine Color Palette
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

        # Determine Size Config
        size_config = self.SIZE_PRESETS.get(size, self.SIZE_PRESETS["medium"])

        # Font Configuration
        font_config = {
            "family": font_family or "Segoe UI, Microsoft YaHei, sans-serif",
            "size": font_size or size_config["font_size"],
            "weight": font_weight or "500"
        }

        self._apply_css(palette, size_config, font_config)

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

            "hover_bg": mix_white(c, 0.8),  # 80% White
            "hover_border": base_hex,  # Base Color
            "hover_text": base_hex,  # Base Color

            "pressed_bg": base_hex,            # Solid Base Color
            "pressed_border": base_hex,        # Solid Base Color
            "pressed_text": "#FFFFFF"          # White Text
        }

    def _apply_css(self, color_palette: dict, size_config: dict, font_config: dict):
        """
        Apply CSS styles with color palette, size configuration, and font settings.
        """
        base_css = f"""
            QPushButton {{
                padding: {size_config['padding']};
                border-radius: {size_config['border_radius']};
                font-family: {font_config['family']};
                font-size: {font_config['size']};
                font-weight: {font_config['weight']};
                border-style: solid;
                border-width: 1px;
            }}
            QPushButton:disabled {{
                background-color: #F5F7FA;
                border-color: #E4E7ED;
                color: #C0C4CC;
            }}
        """

        theme_css = f"""
            QPushButton {{
                background-color: {color_palette['normal_bg']};
                border-color: {color_palette['normal_border']};
                color: {color_palette['normal_text']};
            }}
            QPushButton:hover {{
                background-color: {color_palette['hover_bg']};
                border-color: {color_palette['hover_border']};
                color: {color_palette['hover_text']};
            }}
            QPushButton:pressed {{
                background-color: {color_palette['pressed_bg']};
                border-color: {color_palette['pressed_border']};
                color: {color_palette['pressed_text']};
            }}
        """
        self.setStyleSheet(base_css + theme_css)