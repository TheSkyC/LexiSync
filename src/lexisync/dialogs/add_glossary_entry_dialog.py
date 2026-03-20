# Copyright (c) 2025-2026, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from lexisync.ui_components.banner_overlay import BannerOverlay
from lexisync.utils.constants import SUPPORTED_LANGUAGES
from lexisync.utils.localization import _
from lexisync.utils.path_utils import get_resource_path


class AddGlossaryEntryDialog(QDialog):
    def __init__(self, parent=None, app_instance=None, default_source_lang=None, default_target_lang=None):
        super().__init__(parent)
        self.app = app_instance

        self.setWindowTitle(_("Add Glossary Entry"))
        self.setModal(False)

        self.setAttribute(Qt.WA_DeleteOnClose)

        self.setMinimumWidth(400)

        self._picker_mode = None
        self._picker_banner = None

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.source_term_edit = QLineEdit()
        self.target_term_edit = QLineEdit()
        self.source_lang_combo = QComboBox()
        self.target_lang_combo = QComboBox()
        self.comment_edit = QTextEdit()
        self.comment_edit.setFixedHeight(80)

        crosshair_icon = QIcon(get_resource_path("icons/crosshair.svg"))

        self.src_action = self.source_term_edit.addAction(crosshair_icon, QLineEdit.TrailingPosition)
        self.src_action.setToolTip(_("Pick from Original Text"))
        self.src_action.triggered.connect(lambda: self._on_crosshair_clicked(is_source=True))

        self.tgt_action = self.target_term_edit.addAction(crosshair_icon, QLineEdit.TrailingPosition)
        self.tgt_action.setToolTip(_("Pick from Translation Text"))
        self.tgt_action.triggered.connect(lambda: self._on_crosshair_clicked(is_source=False))

        self._populate_lang_combos()

        if default_source_lang:
            index = self.source_lang_combo.findData(default_source_lang)
            if index != -1:
                self.source_lang_combo.setCurrentIndex(index)

        if default_target_lang:
            index = self.target_lang_combo.findData(default_target_lang)
            if index != -1:
                self.target_lang_combo.setCurrentIndex(index)

        form_layout.addRow(_("Source Term:"), self.source_term_edit)
        form_layout.addRow(_("Source Language:"), self.source_lang_combo)
        form_layout.addRow(_("Target Term:"), self.target_term_edit)
        form_layout.addRow(_("Target Language:"), self.target_lang_combo)
        form_layout.addRow(_("Comment:"), self.comment_edit)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def auto_fill_from_editors(self):
        """首次打开时，自动填充已选中的文本，若无选中则填充全部"""
        if not self.app or not hasattr(self.app, "details_panel"):
            return
        orig_edit = self.app.details_panel.original_text_display
        trans_edit = self.app.details_panel.translation_edit_text

        # 处理原文
        orig_cursor = orig_edit.textCursor()
        if orig_cursor.hasSelection():
            self.source_term_edit.setText(orig_cursor.selectedText())
            orig_cursor.clearSelection()
            orig_edit.setTextCursor(orig_cursor)
        else:
            self.source_term_edit.setText(orig_edit.toPlainText())

        # 处理译文
        trans_cursor = trans_edit.textCursor()
        if trans_cursor.hasSelection():
            self.target_term_edit.setText(trans_cursor.selectedText())
            trans_cursor.clearSelection()
            trans_edit.setTextCursor(trans_cursor)
        else:
            self.target_term_edit.setText(trans_edit.toPlainText())

    def _on_crosshair_clicked(self, is_source):
        if not self.app or not hasattr(self.app, "details_panel"):
            return
        target_edit = (
            self.app.details_panel.original_text_display if is_source else self.app.details_panel.translation_edit_text
        )
        target_line_edit = self.source_term_edit if is_source else self.target_term_edit

        cursor = target_edit.textCursor()
        if cursor.hasSelection():
            # Mode A: 直接提取已选中的文本
            target_line_edit.setText(cursor.selectedText())
            cursor.clearSelection()
            target_edit.setTextCursor(cursor)
        else:
            # Mode B: 进入取词模式
            self._enter_picker_mode(is_source)

    def _enter_picker_mode(self, is_source):
        self._picker_mode = "source" if is_source else "target"

        if not self._picker_banner:
            self._picker_banner = BannerOverlay(self.app.details_panel)

        side_text = _("Original") if is_source else _("Translation")
        msg = _("Picker Mode: Select text in the {side} box... (Press ESC or click elsewhere to cancel)").format(
            side=side_text
        )

        self._picker_banner.show_message(
            msg,
            preset="warning",
            layout_mode="bottom",
            margin=5,
            fixed_height=36,
            interactive=False,
        )

        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if self._picker_mode:
            # 1. ESC 取消
            if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
                self._exit_picker_mode()
                return True

            # 2. 鼠标松开事件
            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                target_edit = (
                    self.app.details_panel.original_text_display
                    if self._picker_mode == "source"
                    else self.app.details_panel.translation_edit_text
                )

                if obj is target_edit.viewport() or obj is target_edit:
                    cursor = target_edit.textCursor()
                    if cursor.hasSelection():
                        line_edit = self.source_term_edit if self._picker_mode == "source" else self.target_term_edit
                        line_edit.setText(cursor.selectedText())
                        cursor.clearSelection()
                        target_edit.setTextCursor(cursor)
                        self._exit_picker_mode()
                        self.activateWindow()
                    return False

                if isinstance(obj, QWidget):
                    window = obj.window()
                    if window is not self:
                        self._exit_picker_mode()
                        return False

        return super().eventFilter(obj, event)

    def _exit_picker_mode(self):
        self._picker_mode = None
        if self._picker_banner:
            self._picker_banner.hide_banner()
        QApplication.instance().removeEventFilter(self)

    def _populate_lang_combos(self):
        for name, code in sorted(SUPPORTED_LANGUAGES.items()):
            self.source_lang_combo.addItem(name, code)
            self.target_lang_combo.addItem(name, code)

    def get_data(self):
        return {
            "source_term": self.source_term_edit.text().strip(),
            "target_term": self.target_term_edit.text().strip(),
            "source_lang": self.source_lang_combo.currentData(),
            "target_lang": self.target_lang_combo.currentData(),
            "comment": self.comment_edit.toPlainText().strip(),
        }

    def accept(self):
        self._exit_picker_mode()

        data = self.get_data()
        if not data["source_term"] or not data["target_term"]:
            QMessageBox.warning(self, _("Missing Information"), _("Source term and target term cannot be empty."))
            return
        if data["source_lang"] == data["target_lang"]:
            QMessageBox.warning(self, _("Invalid Languages"), _("Source and target languages cannot be the same."))
            return
        super().accept()

    def reject(self):
        self._exit_picker_mode()
        super().reject()

    def closeEvent(self, event):
        self._exit_picker_mode()
        super().closeEvent(event)
