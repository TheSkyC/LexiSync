# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QMessageBox, QWidget, QScrollArea, QApplication, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QEvent, QTimer
from PySide6.QtGui import QKeySequence, QAction
from utils.constants import DEFAULT_KEYBINDINGS
from utils.localization import _
import logging

logger = logging.getLogger(__name__)


class KeyCaptureEdit(QLineEdit):
    """
    快捷键捕获控件。
    """
    # 请求开始录制 (发送自己)
    activationRequested = Signal(object)
    # 录制结束 (发送自己)
    recordingFinished = Signal(object)

    def __init__(self, action_key, default_seq, parent=None):
        super().__init__(parent)
        self.action_key = action_key
        self.current_seq = default_seq
        self.setText(default_seq)

        self.setReadOnly(True)
        self.setPlaceholderText(_("Click to set..."))
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.setFocusPolicy(Qt.StrongFocus)

        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._is_recording = False

        self.STYLE_NORMAL = """
            QLineEdit {
                background-color: #FFFFFF;
                border: 2px solid #DCDFE6; /* 统一边框宽度 */
                border-radius: 4px;
                color: #606266;
                padding: 0 5px;
            }
        """
        self.STYLE_RECORDING = """
            QLineEdit { 
                background-color: #E1F5FE; 
                border: 2px solid #03A9F4; /* 统一边框宽度 */
                border-radius: 4px;
                color: #0277BD;
                font-weight: bold;
                padding: 0 5px;
            }
        """
        self.setStyleSheet(self.STYLE_NORMAL)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self._is_recording:
                self.activationRequested.emit(self)
            event.accept()

    def set_recording_state(self, active: bool):
        """由父窗口调用，设置录制状态"""
        if self._is_recording == active:
            return

        self._is_recording = active

        if active:
            self.setStyleSheet(self.STYLE_RECORDING)
            self.setFocus()
            self.style().unpolish(self)
            self.style().polish(self)
            logger.info(f"[KeyBind] {self.action_key} ENTERED recording state")
        else:
            self.setStyleSheet(self.STYLE_NORMAL)
            self.clearFocus()
            self.style().unpolish(self)
            self.style().polish(self)
            logger.info(f"[KeyBind] {self.action_key} EXITED recording state")

    def focusOutEvent(self, event):
        # 如果失去焦点，通知父窗口结束我的录制
        if self._is_recording:
            QTimer.singleShot(10, lambda: self.recordingFinished.emit(self))
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if not self._is_recording:
            return super().keyPressEvent(event)

        key = event.key()
        modifiers = event.modifiers()

        event.accept()

        # 1. 忽略单独的修饰键
        if key in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta]:
            return

        # 2. ESC: 取消
        if key == Qt.Key_Escape:
            self.recordingFinished.emit(self)
            return

        # 3. Backspace/Delete: 清除
        if key in [Qt.Key_Backspace, Qt.Key_Delete]:
            self.current_seq = ""
            self.setText("")
            self.recordingFinished.emit(self)
            return

        # 4. 解析按键
        parts = []
        if modifiers & Qt.ControlModifier: parts.append('Ctrl')
        if modifiers & Qt.ShiftModifier: parts.append('Shift')
        if modifiers & Qt.AltModifier: parts.append('Alt')
        if modifiers & Qt.MetaModifier: parts.append('Meta')

        key_text = QKeySequence(key).toString(QKeySequence.NativeText)
        if not key_text: return

        parts.append(key_text)
        new_sequence = "+".join(parts)

        self.current_seq = new_sequence
        self.setText(new_sequence)

        # 完成录制
        self.recordingFinished.emit(self)


class KeybindingDialog(QDialog):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.editors = []
        self.current_active_editor = None  # 中央状态指针

        self.ACTION_MAP = {
            'open_code_file': self.app.action_open_code_file,
            'open_project': self.app.action_open_project,
            'new_project': self.app.action_new_project,
            'build_project': self.app.action_build_project,
            'save_current_file': self.app.action_save_current_file,
            'save_code_file': self.app.action_save_code_file,
            'undo': self.app.action_undo,
            'redo': self.app.action_redo,
            'find_replace': self.app.action_find_replace,
            'copy_original': self.app.action_copy_original,
            'paste_translation': self.app.action_paste_translation,
            'ai_translate_selected': self.app.action_ai_translate_selected,
            'toggle_reviewed': {'text': _("Toggle Reviewed Status")},
            'toggle_ignored': {'text': _("Toggle Ignored Status")},
            'apply_and_next': {'text': _("Apply and Go to Next Untranslated")},
            'refresh_sort': {'text': _("Refresh View")},
        }

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(550, 650)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        form_layout = QVBoxLayout(scroll_content)
        form_layout.setSpacing(10)

        for action_name, action_obj in self.ACTION_MAP.items():
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)

            if isinstance(action_obj, QAction):
                description = action_obj.text().replace('&', '')
            else:
                description = action_obj['text']

            label = QLabel(description + ":")
            label.setMinimumWidth(200)
            row_layout.addWidget(label)

            current_key = self.app.config['keybindings'].get(
                action_name,
                DEFAULT_KEYBINDINGS.get(action_name, '')
            )

            editor = KeyCaptureEdit(action_name, current_key)
            # 连接信号到中央调度函数
            editor.activationRequested.connect(self.on_editor_request_activation)
            editor.recordingFinished.connect(self.on_editor_finished)

            self.editors.append(editor)

            row_layout.addWidget(editor)
            form_layout.addWidget(row_widget)

        form_layout.addStretch(1)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # 按钮
        button_box = QHBoxLayout()

        reset_btn = QPushButton(_("Reset to Defaults"))
        reset_btn.clicked.connect(self.reset_to_defaults)
        button_box.addWidget(reset_btn)

        button_box.addStretch(1)

        ok_btn = QPushButton(_("OK"))
        ok_btn.clicked.connect(self.accept)
        button_box.addWidget(ok_btn)

        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_box.addWidget(cancel_btn)

        main_layout.addLayout(button_box)

    def on_editor_request_activation(self, editor):
        """
        处理激活请求。
        确保同一时间只有一个 editor 处于录制状态。
        """
        logger.info(f"[KeyBindDialog] Activation requested by: {editor.action_key}")

        # 如果有其他正在录制的，先强制停止它
        if self.current_active_editor and self.current_active_editor != editor:
            logger.info(f"[KeyBindDialog] Stopping previous active: {self.current_active_editor.action_key}")
            self.current_active_editor.set_recording_state(False)

        # 激活新的
        self.current_active_editor = editor
        editor.set_recording_state(True)

    def on_editor_finished(self, editor):
        """
        中央调度：处理结束请求。
        """
        logger.info(f"[KeyBindDialog] Finished signal from: {editor.action_key}")

        # 只有当前激活的 editor 发出的结束信号才有效
        if self.current_active_editor == editor:
            editor.set_recording_state(False)
            self.current_active_editor = None

    def reset_to_defaults(self):
        # 先停止所有活动
        if self.current_active_editor:
            self.current_active_editor.set_recording_state(False)
            self.current_active_editor = None

        reply = QMessageBox.question(self, _("Confirm"),
                                     _("Are you sure you want to reset all keybindings to their default settings?"),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            for editor in self.editors:
                default_val = DEFAULT_KEYBINDINGS.get(editor.action_key, "")
                editor.current_seq = default_val
                editor.setText(default_val)

    def accept(self):
        # 停止当前录制
        if self.current_active_editor:
            self.current_active_editor.set_recording_state(False)
            self.current_active_editor = None

        new_bindings = {}
        seen_keys = {}

        for editor in self.editors:
            key_seq = editor.current_seq.strip()
            action_name = editor.action_key

            if not key_seq:
                new_bindings[action_name] = ""
                continue

            if key_seq in seen_keys:
                conflict_action_key = seen_keys[key_seq]
                conflict_name = conflict_action_key
                if conflict_action_key in self.ACTION_MAP:
                    obj = self.ACTION_MAP[conflict_action_key]
                    if isinstance(obj, QAction):
                        conflict_name = obj.text().replace('&', '')
                    else:
                        conflict_name = obj['text']

                QMessageBox.warning(self, _("Keybinding Conflict"),
                                    _("The key '{key}' is already assigned to '{action}'.\nPlease resolve the conflict.").format(
                                        key=key_seq, action=conflict_name
                                    ))
                return

            seen_keys[key_seq] = action_name
            new_bindings[action_name] = key_seq

        self.app.config['keybindings'] = new_bindings
        self.app.save_config()
        self.app.update_statusbar(_("Keybindings have been updated."))
        super().accept()