# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QListWidget, QStackedWidget,
                               QDialogButtonBox, QListWidgetItem, QVBoxLayout, QLabel,
                               QTabWidget, QFormLayout, QLineEdit, QPushButton,
                               QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
                               QFileDialog, QWidget)
from PySide6.QtCore import Qt
import uuid
import os
import json
from pathlib import Path
import shutil
import copy
from utils.text_utils import format_file_size
from utils.localization import _
from .settings_pages import BaseSettingsPage
from .management_tabs import GlossaryManagementTab, TMManagementTab
from utils.constants import SUPPORTED_LANGUAGES
from services import project_service
from services.code_file_service import extract_translatable_strings
import logging

logger = logging.getLogger(__name__)


class LanguageSelectionDialog(QDialog):
    def __init__(self, parent, existing_langs):
        super().__init__(parent)
        self.setWindowTitle(_("Add Target Language"))
        self.setModal(True)
        self.selected_language = None

        layout = QVBoxLayout(self)
        self.lang_list = QListWidget()

        sorted_langs = sorted(SUPPORTED_LANGUAGES.items())
        for name, code in sorted_langs:
            if code not in existing_langs:
                item = QListWidgetItem(f"{name} ({code})")
                item.setData(Qt.UserRole, code)
                self.lang_list.addItem(item)

        layout.addWidget(QLabel(_("Select a new target language to add to the project:")))
        layout.addWidget(self.lang_list)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        selected_item = self.lang_list.currentItem()
        if selected_item:
            self.selected_language = selected_item.data(Qt.UserRole)
            super().accept()
        else:
            QMessageBox.warning(self, _("No Selection"), _("Please select a language."))


class ProjectGeneralSettingsPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.project_config = copy.deepcopy(self.app.project_config)
        self.changes_made = False

        form_layout = QFormLayout()

        # 项目名称
        self.project_name_edit = QLineEdit(self.project_config.get('name', ''))
        self.project_name_edit.textChanged.connect(self._mark_changed)
        form_layout.addRow(_("Project Name:"), self.project_name_edit)

        # 源语言
        source_lang_code = self.project_config.get('source_language', '')
        source_lang_name = next((name for name, code in SUPPORTED_LANGUAGES.items() if code == source_lang_code),
                                source_lang_code)
        self.source_lang_display = QLineEdit(f"{source_lang_name} ({source_lang_code})")
        self.source_lang_display.setReadOnly(True)
        self.source_lang_display.setToolTip(_("Source language cannot be changed after project creation."))
        form_layout.addRow(_("Source Language:"), self.source_lang_display)

        # 目标语言
        lang_widget = QWidget()
        lang_layout = QVBoxLayout(lang_widget)
        lang_layout.setContentsMargins(0, 0, 0, 0)
        lang_layout.setSpacing(8)  # 增加一些间距

        # 目标语言列表
        self.target_langs_list = QListWidget()
        self.target_langs_list.setMinimumHeight(120)
        self.target_langs_list.setMaximumHeight(200)

        self.target_langs_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #DCDFE6;
                border-radius: 4px;
                background-color: #FFFFFF;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 3px;
                margin: 1px;
            }
            QListWidget::item:selected {
                background-color: #409EFF;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #F5F7FA;
            }
        """)

        self._populate_target_langs()

        # 按钮布局
        lang_buttons_layout = QHBoxLayout()
        lang_buttons_layout.setSpacing(8)

        self.add_lang_button = QPushButton(_("Add..."))
        self.remove_lang_button = QPushButton(_("Remove"))

        # 设置按钮样式和大小
        for btn in [self.add_lang_button, self.remove_lang_button]:
            btn.setMinimumWidth(80)
            btn.setStyleSheet("""
                QPushButton {
                    padding: 6px 12px;
                    border-radius: 4px;
                    border: 1px solid #DCDFE6;
                    background-color: #FFFFFF;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #ECF5FF;
                    color: #409EFF;
                    border-color: #C6E2FF;
                }
                QPushButton:pressed {
                    background-color: #409EFF;
                    color: white;
                }
            """)

        self.add_lang_button.clicked.connect(self._add_language)
        self.remove_lang_button.clicked.connect(self._remove_language)

        lang_buttons_layout.addStretch()
        lang_buttons_layout.addWidget(self.add_lang_button)
        lang_buttons_layout.addWidget(self.remove_lang_button)

        lang_layout.addWidget(self.target_langs_list)
        lang_layout.addLayout(lang_buttons_layout)

        form_layout.addRow(_("Target Languages:"), lang_widget)

        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.page_layout.addLayout(form_layout)
        self.page_layout.addStretch()

    def _populate_target_langs(self):
        self.target_langs_list.clear()
        for lang_code in self.project_config.get('target_languages', []):
            lang_name = next((name for name, code in SUPPORTED_LANGUAGES.items() if code == lang_code), lang_code)
            self.target_langs_list.addItem(f"{lang_name} ({lang_code})")

    def _add_language(self):
        existing_langs = self.project_config.get('target_languages', []) + [self.project_config.get('source_language')]
        dialog = LanguageSelectionDialog(self, existing_langs)
        if dialog.exec():
            new_lang = dialog.selected_language
            if new_lang:
                self.project_config.get('target_languages', []).append(new_lang)
                self._populate_target_langs()
                self._mark_changed()

    def _remove_language(self):
        current_item = self.target_langs_list.currentItem()
        if not current_item:
            QMessageBox.information(self, _("No Selection"), _("Please select a language to remove."))
            return

        lang_text = current_item.text()
        lang_code = lang_text.split('(')[-1].strip(')')

        if len(self.project_config.get('target_languages', [])) <= 1:
            QMessageBox.warning(self, _("Cannot Remove"), _("A project must have at least one target language."))
            return

        reply = QMessageBox.warning(self, _("Confirm Removal"),
                                    _("Are you sure you want to remove the language '{lang}'?\nThis will permanently delete its translation file.").format(
                                        lang=lang_text),
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.project_config.get('target_languages', []).remove(lang_code)
            self._populate_target_langs()
            self._mark_changed()

    def _mark_changed(self):
        self.changes_made = True

    def save_settings(self):
        if not self.changes_made:
            return False

        self.app.project_config['name'] = self.project_name_edit.text()
        self.app.project_config['target_languages'] = self.project_config['target_languages']

        backup_config = self.app.config.get('project_config_backup_on_dialog_open', {})
        old_langs = set(backup_config.get('target_languages', []))
        new_langs = set(self.app.project_config.get('target_languages', []))

        added_langs = new_langs - old_langs
        removed_langs = old_langs - new_langs

        if not added_langs and not removed_langs:
            self.changes_made = False
            return False

        proj_path = Path(self.app.current_project_path)

        for lang in added_langs:
            translation_path = proj_path / project_service.TRANSLATION_DIR / f"{lang}.json"
            if not translation_path.exists():
                if not self.app.project_config.get("source_files"):
                    logger.error("Cannot add new language: No source files in project to create structure from.")
                    continue
                source_file_path = proj_path / self.app.project_config["source_files"][0]["project_path"]
                with open(source_file_path, 'r', encoding='utf-8') as f:
                    content = f.read().replace('\r\n', '\n').replace('\r', '\n')
                patterns = self.app.config.get("extraction_patterns", [])
                initial_objects = [ts.to_dict() for ts in extract_translatable_strings(content, patterns)]
                with open(translation_path, 'w', encoding='utf-8') as f:
                    json.dump(initial_objects, f, indent=4, ensure_ascii=False)

        for lang in removed_langs:
            translation_path = proj_path / project_service.TRANSLATION_DIR / f"{lang}.json"
            if translation_path.exists():
                os.remove(translation_path)
            if self.app.current_target_language == lang:
                if self.app.project_config['target_languages']:
                    self.app.project_config['current_target_language'] = self.app.project_config['target_languages'][0]
                else:
                    self.app.project_config['current_target_language'] = ""

        self.changes_made = False
        return True

class ProjectSourceFilesPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.project_config = copy.deepcopy(self.app.project_config)
        self.changes_made = False

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([_("File Name"), _("Type"), _("Size"), _("Path")])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._populate_files_table()

        buttons_layout = QHBoxLayout()
        add_button = QPushButton(_("Add..."))
        remove_button = QPushButton(_("Remove"))
        rescan_button = QPushButton(_("Re-scan Selected"))
        add_button.clicked.connect(self._add_file)
        remove_button.clicked.connect(self._remove_file)
        rescan_button.clicked.connect(self._rescan_file)
        buttons_layout.addStretch()
        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(remove_button)
        buttons_layout.addWidget(rescan_button)

        self.page_layout.addWidget(self.table)
        self.page_layout.addLayout(buttons_layout)

    def _populate_files_table(self):
        self.table.setRowCount(0)
        for file_info in self.project_config.get('source_files', []):
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)

            filename = Path(file_info['project_path']).name if file_info['project_path'] else Path(
                file_info['original_path']).name
            self.table.setItem(row_position, 0, QTableWidgetItem(filename))
            self.table.setItem(row_position, 1, QTableWidgetItem(file_info['type']))

            size_str = "N/A"
            path_to_check = ""
            if file_info['project_path']:
                path_to_check = os.path.join(self.app.current_project_path, file_info['project_path'])
            else:
                path_to_check = file_info['original_path']

            try:
                if os.path.isfile(path_to_check):
                    size_str = format_file_size(os.path.getsize(path_to_check))
                else:
                    size_str = _("File not found")
            except Exception as e:
                logger.warning(f"Could not get size for {path_to_check}: {e}")
                size_str = _("Error")
            self.table.setItem(row_position, 2, QTableWidgetItem(size_str))
            self.table.setItem(row_position, 3, QTableWidgetItem(file_info['original_path']))
            self.table.item(row_position, 0).setData(Qt.UserRole, file_info['id'])

    def _add_file(self):
        filepath, __ = QFileDialog.getOpenFileName(
            self, _("Select Source File"), "",
            _("All Supported Files (*.ow *.txt *.po *.pot);;All Files (*.*)")
        )
        if not filepath:
            return

        if any(Path(f['original_path']).name == Path(filepath).name for f in self.project_config['source_files']):
            QMessageBox.warning(self, _("File Exists"), _("A file with this name already exists in the project."))
            return

        file_type = 'po' if Path(filepath).suffix.lower() in ['.po', '.pot'] else 'code'
        new_file_entry = {
            "id": str(uuid.uuid4()),
            "original_path": filepath,
            "project_path": "",
            "type": file_type,
            "linked": False
        }
        self.project_config['source_files'].append(new_file_entry)
        self._populate_files_table()
        self._mark_changed()

    def _remove_file(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            return

        if len(self.project_config.get('source_files', [])) <= 1:
            QMessageBox.warning(self, _("Cannot Remove"), _("A project must have at least one source file."))
            return

        file_id = self.table.item(current_row, 0).data(Qt.UserRole)
        file_name = self.table.item(current_row, 0).text()

        reply = QMessageBox.warning(self, _("Confirm Removal"),
                                    _("Are you sure you want to remove '{file}' from the project?\nThis action cannot be undone and will affect all translations.").format(
                                        file=file_name),
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.project_config['source_files'] = [f for f in self.project_config['source_files'] if f['id'] != file_id]
            self._populate_files_table()
            self._mark_changed()

    def _rescan_file(self):
        current_item = self.table.currentItem()
        if not current_item:
            QMessageBox.information(self, _("No Selection"), _("Please select a source file to re-scan."))
            return

        file_id = current_item.data(Qt.UserRole)
        file_info = next((f for f in self.app.project_config['source_files'] if f['id'] == file_id), None)
        if not file_info:
            return

        self.app.rescan_source_file(file_info)


    def _mark_changed(self):
        self.changes_made = True

    def save_settings(self):
        if not self.changes_made:
            return False

        self.app.project_config['source_files'] = self.project_config['source_files']

        proj_path = Path(self.app.current_project_path)

        for file_info in self.app.project_config['source_files']:
            if not file_info['project_path']:
                original_path = Path(file_info['original_path'])
                destination_path = proj_path / project_service.SOURCE_DIR / original_path.name
                shutil.copy2(original_path, destination_path)
                file_info['project_path'] = str(destination_path.relative_to(proj_path).as_posix())

        config_files_on_disk = {f.name for f in (proj_path / project_service.SOURCE_DIR).iterdir()}
        config_files_in_memory = {Path(f['project_path']).name for f in self.app.project_config['source_files']}
        files_to_remove = config_files_on_disk - config_files_in_memory

        for filename in files_to_remove:
            (proj_path / project_service.SOURCE_DIR / filename).unlink(missing_ok=True)

        self.changes_made = False
        return True


class ProjectResourcesPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.page_layout.setContentsMargins(10, 10, 10, 10)
        self.tab_widget = QTabWidget()
        self.page_layout.addWidget(self.tab_widget)
        self.glossary_tab = GlossaryManagementTab(self.app, context="project")
        self.tab_widget.addTab(self.glossary_tab, _("Glossary"))
        self.tm_tab = TMManagementTab(self.app, context="project")
        self.tab_widget.addTab(self.tm_tab, _("Translation Memory"))


class ProjectSettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent

        import copy
        self.app.config['project_config_backup_on_dialog_open'] = copy.deepcopy(self.app.project_config)

        self.setWindowTitle(_("Project Settings"))
        self.setModal(True)
        self.resize(850, 650)
        self.setStyleSheet("""
            QDialog {
                background-color: #F5F7FA;
            }
            QListWidget {
                border: none;
                background-color: #E4E9F2;
                outline: 0;
            }
            QListWidget::item {
                padding: 12px 15px;
                border-radius: 5px;
                font-size: 14px;
            }
            QListWidget::item:selected {
                background-color: #FFFFFF;
                color: #3498DB;
                font-weight: bold;
            }
            QListWidget::item:hover:!selected {
                background-color: #D4DAE5;
            }
            QStackedWidget {
                background-color: #FFFFFF;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                border: 1px solid #DCDFE6;
                background-color: #FFFFFF;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #ECF5FF;
                color: #409EFF;
                border-color: #C6E2FF;
            }
            #okButton {
                background-color: #409EFF;
                color: white;
                border: none;
            }
            #okButton:hover {
                background-color: #66B1FF;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 10)
        main_layout.setSpacing(0)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180)
        content_layout.addWidget(self.nav_list)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)

        main_layout.addLayout(content_layout, 1)

        self.pages = {}
        self.setup_pages()
        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)

        self.button_box = QDialogButtonBox()
        ok_btn = self.button_box.addButton(QDialogButtonBox.Ok)
        ok_btn.setText(_("OK"))
        cancel_btn = self.button_box.addButton(QDialogButtonBox.Cancel)
        cancel_btn.setText(_("Cancel"))

        button_container_layout = QHBoxLayout()
        button_container_layout.setContentsMargins(10, 10, 10, 0)
        button_container_layout.addStretch()
        button_container_layout.addWidget(self.button_box)
        main_layout.addLayout(button_container_layout)

    def setup_pages(self):
        general_page = ProjectGeneralSettingsPage(self.app)
        self._add_page(general_page, _("General"))

        source_files_page = ProjectSourceFilesPage(self.app)
        self._add_page(source_files_page, _("Source Files"))

        resources_page = ProjectResourcesPage(self.app)
        self._add_page(resources_page, _("Project Resources"))

        self.nav_list.setCurrentRow(0)

    def _add_page(self, widget, name):
        self.pages[name] = widget
        self.stack.addWidget(widget)
        self.nav_list.addItem(QListWidgetItem(name))

    def accept(self):
        needs_ui_update = False
        for page_name, page in self.pages.items():
            if hasattr(page, 'save_settings'):
                if page.save_settings():
                    needs_ui_update = True

        if 'project_config_backup_on_dialog_open' in self.app.config:
            del self.app.config['project_config_backup_on_dialog_open']

        project_service.save_project(self.app.current_project_path, self.app)

        if needs_ui_update:
            __, all_strings = project_service.load_project_data(
                project_path=self.app.current_project_path,
                target_language=self.app.current_target_language,
                all_files=True
            )
            self.app.all_project_strings = all_strings
            self.app.loaded_file_ids = {f['id'] for f in self.app.project_config.get('source_files', [])}

            if self.app.current_active_source_file_id:
                self.app._switch_active_file(self.app.current_active_source_file_id)
            else:
                self.app._run_and_refresh_with_validation()
            self.app._update_language_switcher()
        self.app.update_title()
        super().accept()