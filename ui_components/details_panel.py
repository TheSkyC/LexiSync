# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import re
import html
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QSplitter
)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor, QCursor
from services import fix_service
from .tooltip import Tooltip
from .newline_text_edit import NewlineTextEdit
from .elided_label import ElidedLabel
from .syntax_highlighter import TranslationHighlighter
from .styled_button import StyledButton
from utils.localization import _


class DetailsPanel(QWidget):
    apply_translation_signal = Signal()
    ai_translate_signal = Signal()
    translation_text_changed_signal = Signal()
    translation_focus_out_signal = Signal()
    warning_ignored_signal = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_instance = parent
        self._ui_initialized = False
        self.current_ts_obj = None
        self.setup_ui()

    def setup_ui(self):
        if self._ui_initialized:
            return
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        splitter = QSplitter(Qt.Vertical)

        # --- 原文区域 ---
        original_container = QWidget()
        original_layout = QVBoxLayout(original_container)
        original_layout.setContentsMargins(0, 0, 0, 0)
        original_layout.setSpacing(5)

        original_header_layout = QHBoxLayout()
        self.original_label = QLabel(_("Original:"))
        self.original_label.setObjectName("original_label")
        self.original_label.setMinimumHeight(18)

        # Context Badge
        self.context_badge = QLabel(self)
        self.context_badge.setVisible(False)
        self.context_badge.setFixedHeight(18)
        self.context_badge.setAlignment(Qt.AlignCenter)
        self.context_badge.setStyleSheet("""
            QLabel {
                background-color: #E1F5FE;
                color: #0277BD;
                border-radius: 3px;
                padding: 0px 6px;
                font-size: 10px;
                font-weight: bold;
                margin-left: 6px;
                border: 1px solid #B3E5FC;
            }
       """)

        # Format Badge
        self.format_badge = QLabel(self)
        self.format_badge.setVisible(False)
        self.format_badge.setFixedHeight(18)
        self.format_badge.setAlignment(Qt.AlignCenter)
        self.format_badge.setStyleSheet("""
            QLabel {
                background-color: #E0E0E0;
                color: #444444;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
                margin-left: 5px;
            }
        """)

        self.char_count_label = QLabel("")
        self.char_count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        original_header_layout.addWidget(self.original_label)
        original_header_layout.addWidget(self.context_badge)
        original_header_layout.addWidget(self.format_badge)
        original_header_layout.addStretch()
        original_header_layout.addWidget(self.char_count_label)

        original_layout.addLayout(original_header_layout)

        self.original_text_display = NewlineTextEdit()
        self.original_text_display.setReadOnly(True)
        self.original_text_display.setLineWrapMode(NewlineTextEdit.WidgetWidth)
        self.original_text_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        original_layout.addWidget(self.original_text_display)
        self.original_highlighter = TranslationHighlighter(self.original_text_display.document())


        # --- 译文区域 ---
        translation_container = QWidget()
        translation_layout = QVBoxLayout(translation_container)
        translation_layout.setContentsMargins(0, 0, 0, 0)
        translation_layout.setSpacing(5)

        translation_header_layout = QHBoxLayout()
        self.translation_label = QLabel(_("Translation:"))
        self.translation_label.setObjectName("translation_label")
        self.translation_label.setMinimumHeight(20)

        self.warning_banner = QFrame()
        self.warning_banner.setObjectName("warning_banner")
        self.warning_banner.setVisible(False)
        self.warning_banner.setFixedHeight(20)
        self.warning_banner.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.warning_banner.setStyleSheet("""
            #warning_banner {
                background-color: #FFF3CD;
                border: 1px solid #FFEEBA;
                border-radius: 3px;
                margin-left: 10px;
                /* margin-right: 10px;
            }
            QLabel { 
                color: #856404; 
                font-size: 11px;
                border: none;
                background: transparent;
            }
        """)

        banner_layout = QHBoxLayout(self.warning_banner)
        banner_layout.setContentsMargins(4, 0, 4, 0)
        banner_layout.setSpacing(4)

        self.warning_icon_label = QLabel()
        self.warning_icon_label.setFixedSize(12, 12)
        self.warning_icon_label.setScaledContents(True)
        self.warning_icon_label.setStyleSheet("background: transparent; border: none;")

        self.warning_text_label = ElidedLabel()
        self.warning_text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.warning_text_label.installEventFilter(self)

        self.ignore_warning_btn = QPushButton(_("Ignore"))
        self.ignore_warning_btn.setCursor(Qt.PointingHandCursor)
        self.ignore_warning_btn.setFixedSize(40, 16)
        self.ignore_warning_btn.setStyleSheet("""
            QPushButton {
                border: none;
                color: #0056b3;
                text-decoration: underline;
                background: transparent;
                font-weight: bold;
                font-size: 10px;
                padding: 0;
                margin: 0;
                text-align: right;
            }
            QPushButton:hover { color: #003d82; }
        """)
        self.ignore_warning_btn.clicked.connect(self.warning_ignored_signal.emit)

        self.fix_all_btn = QPushButton(_("Auto Fix"))
        self.fix_all_btn.setCursor(Qt.PointingHandCursor)
        self.fix_all_btn.setFixedSize(60, 18)
        self.fix_all_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #28a745;
                border-radius: 3px;
                color: #fff;
                background-color: #28a745;
                font-weight: bold;
                font-size: 10px;
                margin-right: 5px;
            }
            QPushButton:hover { background-color: #218838; }
        """)
        self.fix_all_btn.clicked.connect(self.on_fix_all_clicked)
        self.fix_all_btn.hide()

        # AI Fix
        self.ai_fix_btn = QPushButton(_("AI Fix"))
        self.ai_fix_btn.setCursor(Qt.PointingHandCursor)
        self.ai_fix_btn.setFixedSize(50, 18)
        self.ai_fix_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #673AB7;
                border-radius: 3px;
                color: #fff;
                background-color: #673AB7; /* 深紫色 */
                font-weight: bold;
                font-size: 10px;
                margin-right: 5px;
            }
            QPushButton:hover { background-color: #5E35B1; }
        """)
        self.ai_fix_btn.clicked.connect(self.app_instance.ai_fix_current_item)
        self.ai_fix_btn.hide()

        banner_layout.addWidget(self.warning_icon_label)
        banner_layout.addWidget(self.warning_text_label, 1)
        banner_layout.addWidget(self.fix_all_btn)
        banner_layout.addWidget(self.ai_fix_btn)
        banner_layout.addWidget(self.ignore_warning_btn)

        self.ratio_label = QLabel("")
        self.ratio_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ratio_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        translation_header_layout.addWidget(self.translation_label)
        translation_header_layout.addWidget(self.warning_banner)
        translation_header_layout.addStretch(1)
        translation_header_layout.addWidget(self.ratio_label)
        translation_layout.addLayout(translation_header_layout)

        self.translation_edit_text = NewlineTextEdit()
        self.translation_edit_text.setLineWrapMode(NewlineTextEdit.WidgetWidth)
        self.translation_edit_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.translation_edit_text.textChanged.connect(self.translation_text_changed_signal.emit)
        self.translation_edit_text.focusOutEvent = self._translation_focus_out_event
        translation_layout.addWidget(self.translation_edit_text)

        splitter.addWidget(original_container)
        splitter.addWidget(translation_container)
        splitter.setSizes([100, 100])
        main_layout.addWidget(splitter)

        trans_actions_frame = QFrame()
        trans_actions_layout = QHBoxLayout(trans_actions_frame)
        trans_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_btn = StyledButton(_("Apply Translation"), on_click=self.apply_translation_signal.emit, btn_type="success", size="medium")
        self.apply_btn.setObjectName("apply_btn")
        self.apply_btn.setEnabled(False)
        trans_actions_layout.addWidget(self.apply_btn)

        trans_actions_layout.addStretch(1)

        self.ai_translate_current_btn = StyledButton(_("AI Translate Selected"), on_click=self.ai_translate_signal.emit, btn_type="primary", size="medium")
        self.ai_translate_current_btn.setObjectName("ai_translate_current_btn")
        self.ai_translate_current_btn.setEnabled(False)
        trans_actions_layout.addWidget(self.ai_translate_current_btn)
        main_layout.addWidget(trans_actions_frame)
        self.original_highlighter = TranslationHighlighter(self.original_text_display.document())
        self.highlighter = TranslationHighlighter(self.translation_edit_text.document())

        self.tooltip = Tooltip(self)
        self._ui_initialized = True

    def eventFilter(self, obj, event):
        if obj == self.warning_text_label:
            if event.type() == QEvent.Enter:
                if not self.current_ts_obj:
                    return super().eventFilter(obj, event)

                ts_obj = self.current_ts_obj

                # 过滤掉被忽略的警告
                if ts_obj.is_warning_ignored:
                    return super().eventFilter(obj, event)

                errors = ts_obj.warnings
                warnings = ts_obj.minor_warnings
                infos = ts_obj.infos

                if not errors and not warnings and not infos:
                    return super().eventFilter(obj, event)
                tooltip_parts = []
                if ts_obj.line_num_in_file > 0:
                    tooltip_parts.append(
                        f"<div style='color:#FFFFFF; margin-bottom:5px;'>{_('Line')} {ts_obj.line_num_in_file}</div>")
                groups = [
                    (_("Error"), errors, "#D32F2F"),  # 红色
                    (_("Warning"), warnings, "#F57C00"),  # 橙色
                    (_("Info"), infos, "#1976D2")  # 蓝色
                ]

                for title, msg_list, color in groups:
                    if msg_list:
                        # 组标题
                        tooltip_parts.append(
                            f"<div style='color:{color}; font-weight:bold; margin-top:4px;'>{title}</div>")
                        # 组内容
                        for __, msg in msg_list:
                            tooltip_parts.append(
                                f"<div style='margin-left:10px;'>"
                                f"<span style='color:{color};'>●</span> {msg}"
                                f"</div>"
                            )

                tooltip_html = "".join(tooltip_parts)
                self.tooltip.show_tooltip(QCursor.pos(), tooltip_html)
                return True

            elif event.type() == QEvent.Leave:
                self.tooltip.hide()
            elif event.type() == QEvent.MouseButtonPress:
                self.tooltip.hide()

        return super().eventFilter(obj, event)

    def _translation_focus_out_event(self, event):
        self.translation_focus_out_signal.emit()
        super(NewlineTextEdit, self.translation_edit_text).focusOutEvent(event)

    def update_glossary_highlights(self, matches):
        if hasattr(self, 'original_highlighter'):
            self.original_highlighter.update_glossary(matches)

        if hasattr(self, 'original_text_display'):
            self.original_text_display.set_glossary_matches(matches)

    def apply_placeholder_highlights(self, original_text_widget, translation_text_widget, original_placeholders,
                                     translated_placeholders):
        missing_in_translation = original_placeholders - translated_placeholders

        if hasattr(self, 'highlighter'):
            self.highlighter.update_data(original_placeholders, set())

        if hasattr(self, 'original_highlighter'):
            self.original_highlighter.update_data(original_placeholders, missing_in_translation)

    def on_fix_all_clicked(self):
        if not self.current_ts_obj: return
        target_lang = self.app_instance.current_target_language if self.app_instance.is_project_mode else self.app_instance.target_language

        fixed_text = fix_service.apply_all_fixes(self.current_ts_obj, target_lang)
        if fixed_text:
            self.translation_edit_text.setPlainText(fixed_text)

            cursor = self.translation_edit_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.translation_edit_text.setTextCursor(cursor)
            self.translation_edit_text.setFocus()

            self.app_instance._apply_translation_to_model(self.current_ts_obj, fixed_text, source="auto_fix")
            self.update_warnings(self.current_ts_obj)

    def update_warnings(self, ts_obj):
        self.current_ts_obj = ts_obj
        if not ts_obj:
            self.warning_banner.hide()
            return

        active_msg = None
        style_type = "none"  # error, warning, info

        # Error > Warning > Info
        if ts_obj.warnings and not ts_obj.is_warning_ignored:
            active_msg = ts_obj.warnings[0][1]
            style_type = "error"
        elif ts_obj.minor_warnings and not ts_obj.is_warning_ignored:
            active_msg = ts_obj.minor_warnings[0][1]
            style_type = "warning"
        elif ts_obj.infos and not ts_obj.is_warning_ignored:
            active_msg = ts_obj.infos[0][1]
            style_type = "info"

        if active_msg:
            plain_text_msg = html.unescape(active_msg)
            self.warning_text_label.setText(plain_text_msg)
            self.warning_text_label.setToolTip("")
            if style_type == "error":
                self.warning_banner.setStyleSheet("""
                    #warning_banner { background-color: #F8D7DA; border: 1px solid #F5C6CB; border-radius: 3px; margin-left: 10px; }
                    QLabel { color: #721C24; }
                """)
                icon = self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxCritical)
            elif style_type == "warning":
                self.warning_banner.setStyleSheet("""
                    #warning_banner { background-color: #FFF3CD; border: 1px solid #FFEEBA; border-radius: 3px; margin-left: 10px; }
                    QLabel { color: #856404; }
                """)
                icon = self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxWarning)
            elif style_type == "info":
                self.warning_banner.setStyleSheet("""
                    #warning_banner { background-color: #E3F2FD; border: 1px solid #BBDEFB; border-radius: 3px; margin-left: 10px; }
                    QLabel { color: #0D47A1; }
                """)
                icon = self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxInformation)
            self.warning_icon_label.setPixmap(icon.pixmap(12, 12))

            # Auto Fix
            target_lang = self.app_instance.current_target_language if self.app_instance.is_project_mode else self.app_instance.target_language
            fixed_text = fix_service.apply_all_fixes(ts_obj, target_lang)
            if fixed_text:
                self.fix_all_btn.show()
                self.fix_all_btn.setToolTip(_("Auto-fix: ") + fixed_text)
            else:
                self.fix_all_btn.hide()

            # Ai Fix
            if self.app_instance.config.get("ai_api_key"):
                self.ai_fix_btn.show()
                self.ai_fix_btn.setToolTip(_("Use AI to fix translation errors"))
            else:
                self.ai_fix_btn.hide()

            self.warning_banner.show()
        else:
            self.warning_banner.hide()

    def update_stats_labels(self, char_counts: tuple | None, ratios: tuple | None):
        try:
            if not self.isVisible():
                return

            if char_counts:
                self.char_count_label.setText(f"{char_counts[0]} | {char_counts[1]}")
            else:
                self.char_count_label.setText("")

            if ratios:
                actual_str = f"{ratios[0]:.2f}" if ratios[0] is not None else "-"
                expected_str = f"{ratios[1]:.2f}" if ratios[1] is not None else "-"
                self.ratio_label.setText(f"{actual_str} | {expected_str}")
            else:
                self.ratio_label.setText("")
        except RuntimeError:
            pass

    def update_ui_texts(self):
        self.findChild(QLabel, "original_label").setText(_("Original:"))
        self.findChild(QLabel, "translation_label").setText(_("Translation:"))
        self.findChild(QPushButton, "apply_btn").setText(_("Apply Translation"))
        self.findChild(QPushButton, "ai_translate_current_btn").setText(_("AI Translate Selected"))

    def update_context_badge(self, ts_obj):
        """
        Updates the context badge based on ts_obj.context (msgctxt).
        """
        if ts_obj and ts_obj.context:
            self.context_badge.setText(ts_obj.context)
            self.context_badge.setVisible(True)
        else:
            self.context_badge.setVisible(False)

    def update_format_badge(self, ts_obj):
        """
        Parses the po_comment to find format flags (e.g., python-format) and updates the badge.
        """
        if not ts_obj or not ts_obj.po_comment:
            self.format_badge.setVisible(False)
            return

        from itertools import chain

        flags = set(chain.from_iterable(
            (f.strip() for f in line.replace('#,', '').strip().split(','))
            for line in ts_obj.po_comment.splitlines()
            if line.strip().startswith('#,')
        ))

        format_map = {
            # Python
            'python-format': 'Python',
            'python-brace-format': 'Python Brace',

            # C
            'c-format': 'C',
            'c-sharp-format': 'C#',
            'objc-format': 'Objective-C',

            # Java
            'java-format': 'Java',
            'java-printf-format': 'Java Printf',

            # JavaScript/Web
            'javascript-format': 'JavaScript',
            'typescript-format': 'TypeScript',

            # Shell
            'sh-format': 'Shell',
            'bash-format': 'Bash',
            'perl-format': 'Perl',
            'perl-brace-format': 'Perl Brace',

            # PHP
            'php-format': 'PHP',

            # Qt
            'qt-format': 'Qt',
            'qt-plural-format': 'Qt Plural',

            # Ruby
            'ruby-format': 'Ruby',

            # Lisp
            'lisp-format': 'Lisp',
            'scheme-format': 'Scheme',

            # Others
            'elisp-format': 'Emacs Lisp',
            'librep-format': 'LibRep',
            'smalltalk-format': 'Smalltalk',
            'tcl-format': 'Tcl',
            'awk-format': 'AWK',
            'lua-format': 'Lua',
            'gcc-internal-format': 'GCC Internal',
            'gfc-internal-format': 'GFortran Internal',
            'boost-format': 'Boost',
        }

        found_format = next(
            (format_map[flag] for flag in flags if flag in format_map),
            next(
                (flag.replace('-format', '').capitalize()
                 for flag in flags if flag.endswith('-format')),
                None
            )
        )

        if found_format:
            self.format_badge.setText(f"{found_format} {_('Format')}")
            self.format_badge.setVisible(True)
        else:
            self.format_badge.setVisible(False)