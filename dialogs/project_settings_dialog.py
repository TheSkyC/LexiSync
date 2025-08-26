# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QListWidget, QStackedWidget,
                               QDialogButtonBox, QListWidgetItem, QVBoxLayout, QLabel,
                               QTabWidget)
from utils.localization import _
from .settings_pages import BaseSettingsPage
from .management_tabs import GlossaryManagementTab, TMManagementTab

class ProjectGeneralSettingsPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        label = QLabel(_("Project General Settings.."))
        # TODO: 完善项目设置
        self.page_layout.addWidget(label)
    def save_settings(self): pass

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
        content_layout = QHBoxLayout()
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180)
        self.stack = QStackedWidget()
        content_layout.addWidget(self.nav_list)
        content_layout.addWidget(self.stack)
        main_layout.addLayout(content_layout, 1)

        self.pages = {}
        self.setup_pages()
        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def setup_pages(self):
        general_page = ProjectGeneralSettingsPage(self.app)
        self._add_page(general_page, _("General"))

        resources_page = ProjectResourcesPage(self.app)
        self._add_page(resources_page, _("Project Resources"))

        self.nav_list.setCurrentRow(0)

    def _add_page(self, widget, name):
        self.pages[name] = widget
        self.stack.addWidget(widget)
        self.nav_list.addItem(QListWidgetItem(name))

    def accept(self):
        super().accept()