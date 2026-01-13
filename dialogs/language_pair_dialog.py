# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialogButtonBox, QLineEdit, QListWidget, QListWidgetItem,
    QGroupBox, QTabWidget, QWidget, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from utils.constants import SUPPORTED_LANGUAGES
from utils.localization import _

DIALOG_STYLESHEET = """
    /* 选项卡样式 */
    QTabWidget::pane {
        border: none;
        background: #ffffff;
    }
    QTabBar::tab {
        background: #f5f5f5;
        color: #666666;
        padding: 8px 16px;
        border: none;
        min-width: 120px;
        border-radius: 4px 4px 0 0;
        margin-right: 2px;
    }

    QTabBar::tab:selected {
        background: #ffffff;
        color: #2563eb;
        border-bottom: 2px solid #2563eb;
    }

    /* 搜索框样式 */
    QLineEdit {
        padding: 8px 12px;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        background: #ffffff;
        font-size: 14px;
    }

    QLineEdit:focus {
        border-color: #2563eb;
        outline: none;
    }

    /* 列表样式 */
    QListWidget {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 4px;
        background-color: #ffffff;
    }

    QListWidget::item {
        padding: 8px 12px;
        border-radius: 4px;
        margin: 2px 4px;
    }

    QListWidget::item:selected {
        background-color: #eff6ff;
        color: #2563eb;
        border: none;
    }

    QListWidget::item:hover {
        background-color: #f8fafc;
    }

    /* 分组框样式 */
    QGroupBox {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 24px;
        font-weight: bold;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 8px 12px;
        color: #1f2937;
    }

    /* 按钮样式 */
    QPushButton {
        padding: 8px 16px;
        border-radius: 6px;
        border: 1px solid #d1d5db;
        background-color: #ffffff;
        font-weight: 500;
        min-width: 80px;
    }
    
    QPushButton:hover {
        background-color: #f9fafb;
    }

    QPushButton#okButton {
        background-color: #2563eb;
        color: white;
        border: none;
    }

    QPushButton#okButton:hover {
        background-color: #1d4ed8;
    }

    QPushButton#cancelButton, QPushButton#resetButton {
        background-color: #f3f4f6;
        color: #4b5563;
        border: 1px solid #d1d5db;
    }

    QPushButton#cancelButton:hover, QPushButton#resetButton:hover {
        background-color: #e5e7eb;
    }

    QPushButton[autoDetect="true"], QPushButton#addFavoriteButton, QPushButton#removeFavoriteButton {
        background-color: #f9fafb;
        color: #374151;
        padding: 6px 12px;
        border-radius: 4px;
        border: 1px solid #e5e7eb;
    }

    QPushButton[autoDetect="true"]:hover, QPushButton#addFavoriteButton:hover, QPushButton#removeFavoriteButton:hover {
        background-color: #f3f4f6;
        border-color: #d1d5db;
    }

    /* 当前选择框样式 */
    QFrame#currentSelectionFrame {
        background-color: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
    }
"""

class LanguageListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.setStyleSheet("""
            QListWidget {
                border: 1px solid #DCDFE6;
                border-radius: 4px;
                background-color: #FFFFFF;
                outline: 0;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-bottom: 1px solid #F0F0F0;
                color: #333333;
                border-radius: 2px;
                margin: 1px 2px;
            }
            QListWidget::item:selected {
                background-color: #E6F7FF;
                color: #409EFF;
                border: 1px solid #BAE7FF;
            }
            QListWidget::item:hover:!selected {
                background-color: #F5F7FA;
            }
        """)


class LanguagePairDialog(QDialog):
    def __init__(self, parent, current_source_lang, current_target_lang, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.setWindowTitle(_("Language Pair Settings"))
        self.setModal(True)
        self.resize(550, 650)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)

        self.setStyleSheet(DIALOG_STYLESHEET)

        self.initial_source_lang = current_source_lang
        self.initial_target_lang = current_target_lang
        self.source_lang = current_source_lang
        self.target_lang = current_target_lang

        self.lang_map = SUPPORTED_LANGUAGES
        self.lang_name_list = sorted(list(self.lang_map.keys()))
        self.common_languages = [
            "English",
            "简体中文",
            "Français",
            "Deutsch",
            "Español",
            "Русский",
            "Portuguese",
            "Italiano",
            "Turkish",
            "Arabic",
            "日本語",
            "한국어"
        ]

        self.setup_ui()
        self.setup_connections()
        self._update_all_displays()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        self.tab_widget = QTabWidget()
        self.setup_advanced_tab()
        self.setup_favorites_tab()
        main_layout.addWidget(self.tab_widget)

        self.setup_current_selection_display()
        main_layout.addWidget(self.current_selection_frame)

        self.setup_buttons()
        main_layout.addLayout(self.button_box)


    def setup_advanced_tab(self):
        advanced_widget = QWidget()
        main_hbox = QHBoxLayout(advanced_widget)

        source_group = QGroupBox(_("Source Language"))
        source_vbox = QVBoxLayout(source_group)
        self.source_search = QLineEdit()
        self.source_search.setPlaceholderText(_("Search languages..."))
        self.source_list = LanguageListWidget()
        self.populate_language_list(self.source_list)
        self.source_detect_btn = QPushButton(_("Auto-detect Source"))
        self.source_detect_btn.setProperty("autoDetect", True)
        source_vbox.addWidget(self.source_search)
        source_vbox.addWidget(self.source_list)
        source_vbox.addWidget(self.source_detect_btn)

        target_group = QGroupBox(_("Target Language"))
        target_vbox = QVBoxLayout(target_group)
        self.target_search = QLineEdit()
        self.target_search.setPlaceholderText(_("Search languages..."))
        self.target_list = LanguageListWidget()
        self.populate_language_list(self.target_list)
        self.target_detect_btn = QPushButton(_("Auto-detect Target"))
        self.target_detect_btn.setProperty("autoDetect", True)
        target_vbox.addWidget(self.target_search)
        target_vbox.addWidget(self.target_list)
        target_vbox.addWidget(self.target_detect_btn)

        main_hbox.addWidget(source_group)
        main_hbox.addWidget(target_group)
        self.tab_widget.addTab(advanced_widget, _("Language Selection"))

    def setup_favorites_tab(self):
        favorites_widget = QWidget()
        main_hbox = QHBoxLayout(favorites_widget)

        # 左侧：收藏夹列表
        list_group = QGroupBox(_("Favorite Pairs"))
        list_vbox = QVBoxLayout(list_group)
        self.favorites_list = LanguageListWidget()
        self.favorites_list.itemDoubleClicked.connect(self._on_apply_favorite)
        self.populate_favorites_list()
        list_vbox.addWidget(self.favorites_list)

        # 右侧：操作按钮
        actions_group = QGroupBox(_("Actions"))
        actions_vbox = QVBoxLayout(actions_group)
        self.apply_favorite_btn = QPushButton(_("Apply Favorite"))
        self.apply_favorite_btn.setObjectName("applyFavoriteButton")
        self.add_favorite_btn = QPushButton(_("Add Current Pair to Favorites"))
        self.add_favorite_btn.setObjectName("addFavoriteButton")
        self.remove_favorite_btn = QPushButton(_("Remove Selected Favorite"))
        self.remove_favorite_btn.setObjectName("removeFavoriteButton")

        actions_vbox.addWidget(self.apply_favorite_btn)
        actions_vbox.addSpacing(10)
        actions_vbox.addWidget(self.add_favorite_btn)
        actions_vbox.addWidget(self.remove_favorite_btn)
        actions_vbox.addStretch()
        main_hbox.addWidget(list_group, 3)
        main_hbox.addWidget(actions_group, 0)
        main_hbox.setStretchFactor(list_group, 1)
        main_hbox.setStretchFactor(actions_group, 0)
        self.tab_widget.addTab(favorites_widget, _("Favorite Pairs"))

    def setup_current_selection_display(self):
        self.current_selection_frame = QFrame()
        self.current_selection_frame.setFrameShape(QFrame.StyledPanel)
        self.current_selection_frame.setObjectName("currentSelectionFrame")
        self.current_selection_frame.setStyleSheet(
            "#CurrentSelectionFrame { background-color: #f0f8ff; border: 1px solid #d1e5f7; border-radius: 5px; }")

        layout = QHBoxLayout(self.current_selection_frame)
        layout.setContentsMargins(15, 10, 15, 10)

        label = QLabel(_("Current Selection:"))
        self.current_source_label = QLabel()
        self.current_target_label = QLabel()
        arrow_label = QLabel("→")

        font = QFont("Segoe UI", 11, QFont.Bold)
        self.current_source_label.setFont(font)
        self.current_target_label.setFont(font)
        arrow_label.setFont(font)

        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(self.current_source_label)
        layout.addWidget(arrow_label)
        layout.addWidget(self.current_target_label)
        layout.addStretch()

    def setup_buttons(self):
        self.button_box = QHBoxLayout()
        reset_btn = QPushButton(_("Reset"))
        reset_btn.setObjectName("resetButton")
        reset_btn.clicked.connect(self.reset_to_initial)

        self.button_box.addWidget(reset_btn)
        self.button_box.addStretch()

        button_box_std = QDialogButtonBox()
        ok_btn = button_box_std.addButton(QDialogButtonBox.Ok)
        cancel_btn = button_box_std.addButton(QDialogButtonBox.Cancel)

        ok_btn.setObjectName("okButton")
        cancel_btn.setObjectName("cancelButton")

        ok_btn.setText(_("OK"))
        cancel_btn.setText(_("Cancel"))

        button_box_std.accepted.connect(self.accept)
        button_box_std.rejected.connect(self.reject)
        self.button_box.addWidget(button_box_std)

    def populate_language_list(self, list_widget):
        for lang_name in self.lang_name_list:
            item = QListWidgetItem(lang_name)
            item.setData(Qt.UserRole, self.lang_map[lang_name])
            if lang_name in self.common_languages:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            list_widget.addItem(item)

    def populate_favorites_list(self):
        self.favorites_list.clear()
        pairs = self.app.config.get('favorite_language_pairs', [])
        for src_code, tgt_code in pairs:
            src_name = self.get_language_name(src_code, src_code)
            tgt_name = self.get_language_name(tgt_code, tgt_code)
            item = QListWidgetItem(f"{src_name} → {tgt_name}")
            item.setData(Qt.UserRole, (src_code, tgt_code))
            self.favorites_list.addItem(item)

    def setup_connections(self):
        self.source_search.textChanged.connect(lambda text: self.filter_language_list(self.source_list, text))
        self.target_search.textChanged.connect(lambda text: self.filter_language_list(self.target_list, text))

        self.source_list.currentItemChanged.connect(self._on_source_item_changed)
        self.target_list.currentItemChanged.connect(self._on_target_item_changed)

        self.source_detect_btn.clicked.connect(lambda: self._on_auto_detect('source'))
        self.target_detect_btn.clicked.connect(lambda: self._on_auto_detect('target'))
        self.apply_favorite_btn.clicked.connect(self._on_apply_favorite)
        self.add_favorite_btn.clicked.connect(self._on_add_favorite)
        self.remove_favorite_btn.clicked.connect(self._on_remove_favorite)

    def filter_language_list(self, list_widget, filter_text):
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            item.setHidden(filter_text.lower() not in item.text().lower())

    def _on_source_item_changed(self, current, previous):
        if current:
            self.source_lang = current.data(Qt.UserRole)
            self._update_all_displays()

    def _on_target_item_changed(self, current, previous):
        if current:
            self.target_lang = current.data(Qt.UserRole)
            self._update_all_displays()

    def _on_auto_detect(self, text_type):
        detected_code = self.app.detect_language_from_data(text_type)
        if detected_code:
            if text_type == 'source':
                self.source_lang = detected_code
            else:
                self.target_lang = detected_code
            self._update_all_displays()

    def _on_apply_favorite(self):
        selected_items = self.favorites_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        self.source_lang, self.target_lang = item.data(Qt.UserRole)
        self._update_all_displays()
        self.tab_widget.setCurrentIndex(0)

    def _on_add_favorite(self):
        pair = [self.source_lang, self.target_lang]
        favorites = self.app.config.get('favorite_language_pairs', [])
        if pair not in favorites:
            favorites.append(pair)
            self.app.config['favorite_language_pairs'] = favorites
            self.app.save_config()
            self.populate_favorites_list()

    def _on_remove_favorite(self):
        selected_items = self.favorites_list.selectedItems()
        if not selected_items:
            return
        item_to_remove = selected_items[0]
        pair_to_remove = list(item_to_remove.data(Qt.UserRole))
        favorites = self.app.config.get('favorite_language_pairs', [])
        if pair_to_remove in favorites:
            favorites.remove(pair_to_remove)
            self.app.config['favorite_language_pairs'] = favorites
            self.app.save_config()
            self.populate_favorites_list()

    def get_language_name(self, lang_code, fallback=""):
        for name, code in self.lang_map.items():
            if code == lang_code:
                return name
        return fallback

    def _update_all_displays(self):
        source_name = self.get_language_name(self.source_lang, self.source_lang)
        target_name = self.get_language_name(self.target_lang, self.target_lang)

        self.select_in_list(self.source_list, source_name)
        self.select_in_list(self.target_list, target_name)

        self.current_source_label.setText(source_name)
        self.current_target_label.setText(target_name)

    def select_in_list(self, list_widget, lang_name):
        list_widget.blockSignals(True)
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.text() == lang_name:
                list_widget.setCurrentItem(item)
                list_widget.scrollToItem(item, QListWidget.EnsureVisible)
                break
        list_widget.blockSignals(False)

    def reset_to_initial(self):
        self.source_lang = self.initial_source_lang or 'en'
        self.target_lang = self.initial_target_lang or 'zh'
        self._update_all_displays()

    def accept(self):
        if self.source_lang == self.target_lang:
            QMessageBox.warning(self, _("Warning"), _("Source and target languages cannot be the same."))
            return
        super().accept()