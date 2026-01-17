# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QGroupBox, QSplitter, QWidget, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from utils.localization import _
from services.smart_translation_service import SmartTranslationService
import json
import re


class RegexGenWorker(QThread):
    finished = Signal(bool, dict, str)  # success, data, error_msg

    def __init__(self, app, sample, target, context):
        super().__init__()
        self.app = app
        self.sample = sample
        self.target = target
        self.context = context
        self._is_cancelled = False

    def cancel(self):
        """请求取消当前操作"""
        self._is_cancelled = True

    def run(self):
        try:
            if self._is_cancelled:
                return

            prompt = self._build_prompt()
            response = self.app.ai_translator.translate(
                self.sample, prompt, temperature=0.1
            )

            if self._is_cancelled:
                return

            data = self._parse_json(response)

            # 验证结构
            if not all(k in data for k in ("left", "right")):
                raise ValueError("AI response missing required fields 'left' or 'right'.")

            # 验证正则表达式语法
            self._validate_regex_syntax(data)

            self.finished.emit(True, data, "")

        except Exception as e:
            if not self._is_cancelled:
                self.finished.emit(False, {}, str(e))

    def _validate_regex_syntax(self, data):
        """验证正则表达式语法是否有效"""
        try:
            re.compile(data["left"])
            re.compile(data["right"])
        except re.error as e:
            raise ValueError(f"Invalid regex syntax: {str(e)}")

    def _parse_json(self, text):
        """改进的JSON解析,支持多种格式"""
        original_text = text

        # 1. 移除 Markdown 代码块
        text = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text.strip())

        # 2. 移除可能的前导/尾随文本说明
        # AI有时会添加 "Here's the result:" 之类的说明
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            text = json_match.group(0)

        # 3. 尝试标准 JSON 解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 4. 尝试修复常见问题:单引号转双引号
        try:
            # 将单引号键名转为双引号
            fixed_text = re.sub(r"'(\w+)':", r'"\1":', text)
            # 将单引号值转为双引号(简单情况)
            fixed_text = re.sub(r":\s*'([^']*)'", r': "\1"', fixed_text)
            return json.loads(fixed_text)
        except json.JSONDecodeError:
            pass

        raise ValueError(
            f"Failed to parse AI response as JSON.\n"
            f"Please try again or adjust your input.\n\n"
            f"Raw response preview:\n{original_text[:200]}..."
        )

    def _build_prompt(self):
        """构建优化后的prompt"""
        context_section = ""
        if self.context:
            context_section = f"\n### Additional Context\n{self.context}\n"

        return (
            "You are a Regex Pattern Expert. Generate Python regular expressions to extract specific content.\n\n"

            "### Task\n"
            "Identify patterns that appear immediately BEFORE and AFTER the target content.\n"
            "We'll use these as delimiters: LEFT_PATTERN + [TARGET_CONTENT] + RIGHT_PATTERN\n\n"

            f"### Sample Text\n```\n{self.sample}\n```\n\n"

            f"### Target Content to Extract\n```\n{self.target}\n```\n"

            f"{context_section}\n"

            "### Requirements\n"
            "1. **left**: Regex matching text immediately BEFORE target\n"
            "2. **right**: Regex matching text immediately AFTER target\n"
            "3. **multiline**: Boolean (true if target spans multiple lines)\n"
            "4. Use `\\s*` for flexible whitespace matching\n"
            "5. Escape special regex characters: . * + ? [ ] ( ) { } ^ $ | \\\n"
            "6. **CRITICAL**: In JSON strings, backslashes must be escaped.\n"
            "   - For digit: use `\\\\d`\n"
            "   - For whitespace: use `\\\\s`\n"
            "   - For literal dot: use `\\\\.`\n\n"

            "### Output Format (JSON only, no explanations)\n"
            "```json\n"
            "{\n"
            '  "left": "pattern_before_target",\n'
            '  "right": "pattern_after_target",\n'
            '  "multiline": false\n'
            "}\n"
            "```\n\n"

            "Return ONLY the JSON object. No markdown fences, no explanations."
        )


class AIRegexGeneratorDialog(QDialog):
    def __init__(self, parent, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.result = None
        self.generated_data = None
        self.worker = None

        self.setWindowTitle(_("AI Regex Generator"))
        self.resize(900, 700)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. Input Area
        input_group = QGroupBox(_("Input"))
        input_layout = QVBoxLayout(input_group)

        # Sample
        input_layout.addWidget(QLabel(_("1. Paste Sample Text (The full content):")))
        self.sample_edit = QTextEdit()
        self.sample_edit.setPlaceholderText(_("e.g. var myString = \"Hello World\";"))
        self.sample_edit.setFixedHeight(150)
        input_layout.addWidget(self.sample_edit)

        # Target
        input_layout.addWidget(QLabel(_("2. Paste Target Content (What you want to extract):")))
        self.target_edit = QTextEdit()
        self.target_edit.setPlaceholderText(_("e.g. Hello World"))
        self.target_edit.setFixedHeight(60)
        input_layout.addWidget(self.target_edit)

        # Context
        input_layout.addWidget(QLabel(_("3. Additional Hint (Optional):")))
        self.hint_edit = QTextEdit()
        self.hint_edit.setPlaceholderText(_("e.g. Extract content inside double quotes, ignore escaped quotes."))
        self.hint_edit.setFixedHeight(50)
        input_layout.addWidget(self.hint_edit)

        layout.addWidget(input_group)

        # Generate Button & Progress
        gen_layout = QHBoxLayout()
        self.btn_generate = QPushButton(_("✨ AI Generate"))
        self.btn_generate.setStyleSheet("background-color: #673AB7; color: white; font-weight: bold; padding: 8px;")
        self.btn_generate.clicked.connect(self.start_generation)
        gen_layout.addWidget(self.btn_generate)

        self.btn_cancel = QPushButton(_("Cancel"))
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self.cancel_generation)
        gen_layout.addWidget(self.btn_cancel)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # Infinite loop
        gen_layout.addWidget(self.progress_bar)

        layout.addLayout(gen_layout)

        # 2. Result Area
        result_group = QGroupBox(_("AI Suggestion"))
        result_layout = QVBoxLayout(result_group)

        # Left
        result_layout.addWidget(QLabel(_("Left Delimiter:")))
        self.res_left = QTextEdit()
        self.res_left.setReadOnly(True)
        self.res_left.setFixedHeight(40)
        self.res_left.setStyleSheet("background-color: #F0F0F0;")
        result_layout.addWidget(self.res_left)

        # Right
        result_layout.addWidget(QLabel(_("Right Delimiter:")))
        self.res_right = QTextEdit()
        self.res_right.setReadOnly(True)
        self.res_right.setFixedHeight(40)
        self.res_right.setStyleSheet("background-color: #F0F0F0;")
        result_layout.addWidget(self.res_right)

        # Multiline
        self.lbl_multiline = QLabel(_("Multiline Mode: Unknown"))
        result_layout.addWidget(self.lbl_multiline)

        # Validation
        self.lbl_validation = QLabel("")
        self.lbl_validation.setWordWrap(True)
        result_layout.addWidget(self.lbl_validation)

        layout.addWidget(result_group)

        # Buttons
        btn_box = QHBoxLayout()
        self.btn_apply = QPushButton(_("Apply to Rule"))
        self.btn_apply.clicked.connect(self.apply_result)
        self.btn_apply.setEnabled(False)

        btn_close = QPushButton(_("Cancel"))
        btn_close.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(self.btn_apply)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def start_generation(self):
        sample = self.sample_edit.toPlainText().strip()
        target = self.target_edit.toPlainText().strip()

        if not sample or not target:
            QMessageBox.warning(
                self,
                _("Missing Input"),
                _("Please provide both Sample Text and Target Content.")
            )
            return

        # 规范化比较 (忽略首尾空白)
        if target not in sample:
            QMessageBox.warning(
                self,
                _("Invalid Input"),
                _("The Target Content must exist within the Sample Text.\n"
                  "Please make sure you copied the exact text.")
            )
            return

        if not self.app.config.get("ai_api_key"):
            QMessageBox.critical(
                self,
                _("AI Error"),
                _("AI API Key is missing. Please configure it in Settings.")
            )
            return

        # UI状态
        self.btn_generate.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.progress_bar.setVisible(True)
        self.lbl_validation.setText(_("Generating..."))
        self.btn_apply.setEnabled(False)

        # 启动worker
        self.worker = RegexGenWorker(
            self.app,
            sample,
            target,
            self.hint_edit.toPlainText()
        )
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.start()

    def cancel_generation(self):
        """取消生成"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)  # 等待最多2秒

        self.btn_generate.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.progress_bar.setVisible(False)
        self.lbl_validation.setText(_("Generation cancelled."))

    def on_generation_finished(self, success, data, error):
        self.btn_generate.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.progress_bar.setVisible(False)

        if not success:
            # 友好的错误提示
            error_msg = _("Failed to generate regex pattern.")
            if "parse" in error.lower() or "json" in error.lower():
                error_msg += "\n" + _("The AI response format was invalid. Please try again.")
            elif "api" in error.lower() or "key" in error.lower():
                error_msg += "\n" + _("There was an API error. Please check your settings.")
            else:
                error_msg += f"\n\n{_('Technical details')}: {error[:100]}"

            QMessageBox.critical(self, _("Generation Failed"), error_msg)
            return

        # 显示结果
        self.generated_data = data
        self.res_left.setPlainText(data.get("left", ""))
        self.res_right.setPlainText(data.get("right", ""))
        is_multi = data.get("multiline", False)
        self.lbl_multiline.setText(f"{_('Multiline Mode')}: {'ON' if is_multi else 'OFF'}")

        # 自动验证
        self.validate_regex(data)
        self.btn_apply.setEnabled(True)

    def validate_regex(self, data):
        """验证生成的正则表达式"""
        try:
            left = data["left"]
            right = data["right"]
            is_multi = data.get("multiline", False)

            flags = re.DOTALL if is_multi else 0
            pattern = re.compile(f"({left})(.*?)({right})", flags)

            sample = self.sample_edit.toPlainText()
            target = self.target_edit.toPlainText()

            match = pattern.search(sample)

            if match:
                extracted = match.group(2)
                # 更宽松的比较:去除首尾空白
                if extracted.strip() == target.strip():
                    self.lbl_validation.setText(
                        f"<font color='green'><b>✓ {_('Perfect Match!')}</b></font>"
                    )
                else:
                    # 显示差异
                    self.lbl_validation.setText(
                        f"<font color='orange'><b>⚠ {_('Partial Match')}</b><br>"
                        f"{_('Expected')}: <code>{self._escape_html(target[:50])}</code><br>"
                        f"{_('Extracted')}: <code>{self._escape_html(extracted[:50])}</code></font>"
                    )
            else:
                self.lbl_validation.setText(
                    f"<font color='red'><b>✗ {_('No match found')}</b><br>"
                    f"{_('The pattern did not match in the sample text.')}</font>"
                )

        except re.error as e:
            self.lbl_validation.setText(
                f"<font color='red'><b>✗ {_('Invalid Regex')}</b><br>{str(e)}</font>"
            )
        except Exception as e:
            self.lbl_validation.setText(
                f"<font color='red'><b>✗ {_('Validation Error')}</b><br>{str(e)}</font>"
            )

    def _escape_html(self, text):
        """转义HTML特殊字符"""
        return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    def apply_result(self):
        """应用结果"""
        if not self.generated_data or not self.res_left.toPlainText():
            QMessageBox.warning(
                self,
                _("No Result"),
                _("Please generate a regex pattern first.")
            )
            return

        self.result = {
            "left": self.res_left.toPlainText(),
            "right": self.res_right.toPlainText(),
            "multiline": "ON" in self.lbl_multiline.text()
        }
        self.accept()

    def closeEvent(self, event):
        """确保关闭时停止worker"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1000)
        event.accept()