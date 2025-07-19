# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QDialog, QHBoxLayout, QListWidget, QStackedWidget, QDialogButtonBox, QListWidgetItem, \
    QPushButton, QVBoxLayout, QWidget, QMessageBox
from PySide6.QtCore import Qt
from utils.localization import _
from .settings_pages import GeneralSettingsPage, AppearanceSettingsPage, AISettingsPage, ValidationSettingsPage


class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.setWindowTitle(_("Settings"))
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
        self.apply_button = self.button_box.addButton(_("Apply"), QDialogButtonBox.ApplyRole)
        ok_btn = self.button_box.addButton(QDialogButtonBox.Ok)
        ok_btn.setObjectName("okButton")
        self.button_box.addButton(QDialogButtonBox.Cancel)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.apply_button.clicked.connect(self.on_apply_button_clicked)

        button_container_layout = QHBoxLayout()
        button_container_layout.setContentsMargins(10, 10, 10, 0)
        button_container_layout.addStretch()
        button_container_layout.addWidget(self.button_box)
        main_layout.addLayout(button_container_layout)

    def setup_pages(self):
        general_page = GeneralSettingsPage(self.app)
        self._add_page(general_page, _("General"))

        appearance_page = AppearanceSettingsPage(self.app)
        self._add_page(appearance_page, _("Appearance"))

        ai_page = AISettingsPage(self.app)
        self._add_page(ai_page, _("AI Translation"))

        validation_page = ValidationSettingsPage(self.app)
        self._add_page(validation_page, _("Validation"))

        self.nav_list.setCurrentRow(0)

    def _add_page(self, widget, name):
        self.pages[name] = widget
        self.stack.addWidget(widget)
        self.nav_list.addItem(QListWidgetItem(name))

    def apply_changes(self):
        language_was_changed = False
        for page in self.pages.values():
            if hasattr(page, 'save_settings'):
                result = page.save_settings()
                if result is True:
                    language_was_changed = True

        self.app.save_config()
        self.app.update_statusbar(_("Settings applied."), persistent=False)

        return language_was_changed

    def accept(self):
        self.apply_changes()
        super().accept()

    def on_apply_button_clicked(self):
        language_changed = self.apply_changes()
        if language_changed:
            QMessageBox.information(self,
                                    _("Language Changed"),
                                    _("The UI language has been changed.\nSome changes may require a restart of the application to take full effect.")
                                    )