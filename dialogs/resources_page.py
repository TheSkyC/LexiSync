# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QTabWidget, QLabel
from .settings_pages import BaseSettingsPage
from .management_tabs import GlossaryManagementTab, TMManagementTab
from utils.localization import _

class ResourcesSettingsPage(BaseSettingsPage):
    def __init__(self, app_instance, context: str):
        super().__init__()
        self.app = app_instance
        self.context = context

        self.page_layout.setContentsMargins(10, 10, 10, 10)

        self.tab_widget = QTabWidget()
        self.page_layout.addWidget(self.tab_widget)

        self.glossary_tab = GlossaryManagementTab(self.app, self.context)
        self.tab_widget.addTab(self.glossary_tab, _("Glossary"))

        self.tm_tab = TMManagementTab(self.app, self.context)
        self.tab_widget.addTab(self.tm_tab, _("Translation Memory"))

    def save_settings(self):
        pass