# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QListWidget, QStackedWidget,
                               QListWidgetItem,QVBoxLayout, QMessageBox)
from ui_components.styled_button import StyledButton
from .settings_pages import GeneralSettingsPage, AppearanceSettingsPage, AISettingsPage, ValidationSettingsPage
from .resources_page import ResourcesSettingsPage
from utils.localization import _
import logging
logger = logging.getLogger(__name__)


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

        # Button
        button_container_layout = QHBoxLayout()
        button_container_layout.setContentsMargins(0, 10, 10, 0)
        button_container_layout.setSpacing(15)
        button_container_layout.addStretch()

        # Apply
        self.apply_button = StyledButton(_("Apply"), on_click=self.on_apply_button_clicked, btn_type="success")
        button_container_layout.addWidget(self.apply_button)
        # OK
        self.ok_button = StyledButton(_("OK"), on_click=self.accept, btn_type="primary")
        button_container_layout.addWidget(self.ok_button)
        # Cancel
        self.cancel_button = StyledButton(_("Cancel"), on_click=self.reject, btn_type="default")
        button_container_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_container_layout)

    def setup_pages(self):
        general_page = GeneralSettingsPage(self.app)
        self._add_page(general_page, _("General"))

        appearance_page = AppearanceSettingsPage(self.app)
        self._add_page(appearance_page, _("Appearance"))

        ai_page = AISettingsPage(self.app)
        self._add_page(ai_page, _("AI Assistance"))

        validation_page = ValidationSettingsPage(self.app)
        self._add_page(validation_page, _("Validation"))

        resources_page = ResourcesSettingsPage(self.app, context="global")
        self._add_page(resources_page, _("Global Resources"))

        if hasattr(self.app, 'plugin_manager'):
            plugin_pages_data = self.app.plugin_manager.run_hook('register_settings_pages')
            if plugin_pages_data:
                all_plugin_pages = {}
                for page_dict in plugin_pages_data:
                    all_plugin_pages.update(page_dict)

                if all_plugin_pages:
                    for page_title, page_class in sorted(all_plugin_pages.items()):
                        try:
                            page_instance = page_class(self.app)
                            self._add_page(page_instance, page_title)
                        except Exception as e:
                            logger.error(f"Error instantiating settings page for '{page_title}': {e}")

        self.nav_list.setCurrentRow(0)

    def _add_page(self, widget, name):
        self.pages[name] = widget
        self.stack.addWidget(widget)
        self.nav_list.addItem(QListWidgetItem(name))

    def apply_changes(self):
        language_was_changed = False
        for page_widget in self.pages.values():
            if hasattr(page_widget, 'save_settings'):
                try:
                    result = page_widget.save_settings()
                    if result is True:
                        language_was_changed = True
                except Exception as e:
                    page_title = ""
                    for title, widget_instance in self.pages.items():
                        if widget_instance == page_widget:
                            page_title = title
                            break
                    logger.error(f"Error saving settings for page '{page_title}': {e}")
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