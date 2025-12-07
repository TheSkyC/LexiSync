# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QMenu, QGroupBox, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QCursor
from utils.localization import _
import os
import logging

logger = logging.getLogger(__name__)


class ResourceViewerDialog(QDialog):
    data_updated = Signal()

    DEFAULT_PAGE_SIZE = 100
    COLUMN_ID = 0
    COLUMN_SOURCE = 1
    COLUMN_TARGET = 2
    COLUMN_SRC_LANG = 3
    COLUMN_TGT_LANG = 4
    COLUMN_SOURCE_FILE = 5

    def __init__(self, parent, app_instance, mode='tm', initial_source_key=None, initial_db_type=None):
        super().__init__(parent)
        self.app = app_instance
        self.mode = mode
        self.initial_source_key = initial_source_key
        self.initial_db_type = initial_db_type

        self._init_service()

        # 分页
        self.current_page = 1
        self.page_size = self.DEFAULT_PAGE_SIZE
        self.total_count = 0

        # UI
        self._setup_window()
        self.setup_ui()

        self._load_initial_data()

    def _init_service(self):
        """初始化服务"""
        if self.mode == 'tm':
            self.service = self.app.tm_service
            self.title_prefix = _("Translation Memory Viewer")
        else:
            self.service = self.app.glossary_service
            self.title_prefix = _("Glossary Viewer")

        self.db_path = None

    def _setup_window(self):
        self.setWindowTitle(self.title_prefix)
        self.resize(1000, 700)
        self.setModal(False)
        self.setWindowFlags(Qt.Window)

    def _load_initial_data(self):

        try:
            self.on_db_changed(self.db_selector.currentIndex())
        except Exception as e:
            logger.error(f"Failed to load initial data: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                _("Error"),
                _("Failed to load data: {error}").format(error=str(e))
            )

    def on_db_changed(self, index):
        try:
            # 更新数据库路径
            db_type = self.db_selector.itemData(index)
            self.db_path = (
                self.service.project_db_path if db_type == "project"
                else self.service.global_db_path
            )

            if not self.db_path or not os.path.exists(self.db_path):
                logger.warning(f"Database path does not exist: {self.db_path}")
                self._clear_all_data()
                return

            # 重置所有筛选器
            self._reset_all_filters()

            # 重新加载数据
            self.load_filter_options()
            self.current_page = 1
            self.load_data()

        except Exception as e:
            logger.error(f"Failed to change database: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                _("Error"),
                _("Failed to switch database: {error}").format(error=str(e))
            )

    def _reset_all_filters(self):
        for combo in [self.source_combo, self.src_lang_combo, self.tgt_lang_combo]:
            combo.blockSignals(True)
            combo.clear()

        self.source_combo.addItem(_("All Sources"), "All")
        self.src_lang_combo.addItem(_("All Source Langs"), "All")
        self.tgt_lang_combo.addItem(_("All Target Langs"), "All")

        for combo in [self.source_combo, self.src_lang_combo, self.tgt_lang_combo]:
            combo.blockSignals(False)

        self.search_edit.clear()

    def _clear_all_data(self):
        self.table.setRowCount(0)
        self.total_count = 0
        self._update_pagination_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # 1. Type & Database
        main_layout.addLayout(self._create_scope_section())

        # 2. 筛选
        main_layout.addWidget(self._create_filter_section())

        # 3. 数据表格
        main_layout.addWidget(self._create_table())

        # 4. 分页控件
        main_layout.addLayout(self._create_pagination_section())

    def _create_scope_section(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 资源类型选择器
        layout.addWidget(QLabel(_("Type:")))
        self.mode_selector = QComboBox()
        self.mode_selector.addItem(_("Translation Memory"), "tm")
        self.mode_selector.addItem(_("Glossary"), "glossary")

        initial_index = self.mode_selector.findData(self.mode)
        if initial_index != -1:
            self.mode_selector.setCurrentIndex(initial_index)
        self.mode_selector.currentIndexChanged.connect(self.on_mode_changed)
        layout.addWidget(self.mode_selector)

        layout.addSpacing(20)

        # 数据库选择器
        layout.addWidget(QLabel(_("Database:")))
        self.db_selector = self._create_db_selector()
        layout.addWidget(self.db_selector)
        layout.addStretch()

        return layout

    def _create_filter_section(self):
        filter_group = QGroupBox(_("Filters"))
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.setContentsMargins(10, 10, 10, 10)
        filter_layout.setSpacing(10)

        # Source
        filter_layout.addWidget(QLabel(_("Source:")))
        self.source_combo = QComboBox()
        self.source_combo.addItem(_("All Sources"), "All")
        self.source_combo.setMinimumWidth(120)
        self.source_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        filter_layout.addWidget(self.source_combo)

        # Src Lang
        filter_layout.addWidget(QLabel(_("Src:")))
        self.src_lang_combo = QComboBox()
        self.src_lang_combo.addItem(_("All"), "All")
        filter_layout.addWidget(self.src_lang_combo)

        # Tgt Lang
        filter_layout.addWidget(QLabel(_("Tgt:")))
        self.tgt_lang_combo = QComboBox()
        self.tgt_lang_combo.addItem(_("All"), "All")
        filter_layout.addWidget(self.tgt_lang_combo)

        # Search Box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(_("Search text..."))
        self.search_edit.returnPressed.connect(self.on_search)
        self.search_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        filter_layout.addWidget(self.search_edit)

        # Buttons
        search_btn = QPushButton(_("Search"))
        search_btn.clicked.connect(self.on_search)
        filter_layout.addWidget(search_btn)

        reset_btn = QPushButton(_("Reset"))
        reset_btn.clicked.connect(self.reset_filters)
        filter_layout.addWidget(reset_btn)

        filter_layout.setStretchFactor(self.source_combo, 1)
        filter_layout.setStretchFactor(self.search_edit, 2)

        return filter_group

    def on_mode_changed(self, index):
        """切换资源类型 (TM <-> Glossary)"""
        new_mode = self.mode_selector.itemData(index)
        if new_mode == self.mode:
            return

        self.mode = new_mode
        self._init_service()
        self.setWindowTitle(self.title_prefix)
        self.initial_source_key = None
        self.on_db_changed(self.db_selector.currentIndex())

    def _create_db_selector(self):
        """创建数据库选择器"""
        selector = QComboBox()
        if self.app.is_project_mode:
            selector.addItem(_("Project Resource"), "project")
            selector.addItem(_("Global Resource"), "global")
        else:
            selector.addItem(_("Global Resource"), "global")

        if self.initial_db_type:
            index = selector.findData(self.initial_db_type)
            if index != -1:
                selector.setCurrentIndex(index)

        selector.currentIndexChanged.connect(self.on_db_changed)
        return selector

    def _create_table(self):
        """创建数据表格"""
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID",
            _("Source Text"),
            _("Target Text"),
            _("Src"),
            _("Tgt"),
            _("Source File")
        ])
        self.table.hideColumn(self.COLUMN_ID)

        # 设置列宽策略
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COLUMN_SOURCE, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COLUMN_TARGET, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COLUMN_SRC_LANG, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COLUMN_TGT_LANG, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COLUMN_SOURCE_FILE, QHeaderView.ResizeToContents)

        # 设置选择和编辑行为
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table.cellChanged.connect(self.on_cell_changed)

        # 右键菜单
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        return self.table

    def _create_pagination_section(self):
        """创建分页控件"""
        pagination_layout = QHBoxLayout()

        self.prev_btn = QPushButton("<< " + _("Previous"))
        self.prev_btn.clicked.connect(self.prev_page)

        self.page_label = QLabel(_("Page 1 / 1"))

        self.next_btn = QPushButton(_("Next") + " >>")
        self.next_btn.clicked.connect(self.next_page)

        self.total_label = QLabel(_("Total: 0"))

        pagination_layout.addWidget(self.total_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.prev_btn)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_btn)
        pagination_layout.addStretch()

        return pagination_layout

    def load_filter_options(self):
        """加载筛选选项"""
        try:
            if not self.db_path or not os.path.exists(self.db_path):
                logger.warning(f"Cannot load filter options: invalid db_path {self.db_path}")
                return

            # 加载来源列表
            self._load_source_options()

            # 加载语言列表
            self._load_language_options()

        except Exception as e:
            logger.error(f"Failed to load filter options: {e}", exc_info=True)

    def _load_source_options(self):
        """加载来源选项"""
        try:
            manifest_path = os.path.join(os.path.dirname(self.db_path), "manifest.json")

            if self.mode == 'tm':
                manifest = self.app.tm_service._read_manifest(manifest_path)
                manual_key = 'manual'
            else:
                manifest = self.app.glossary_service._read_manifest(manifest_path)
                manual_key = 'manual_project' if self.app.is_project_mode else 'manual_global'

            sources = list(manifest.get("imported_sources", {}).keys())

            # 检查是否有手动录入
            if self.service.get_entry_count_by_source(
                    os.path.dirname(self.db_path), manual_key
            ) > 0:
                sources.insert(0, manual_key)

            # 添加到下拉框
            self.source_combo.addItems(sources)

            # 如果有初始筛选，选中它
            if self.initial_source_key:
                index = self.source_combo.findText(self.initial_source_key)
                if index != -1:
                    self.source_combo.setCurrentIndex(index)

        except Exception as e:
            logger.error(f"Failed to load source options: {e}", exc_info=True)

    def _load_language_options(self):
        """加载语言选项"""
        try:
            srcs, tgts = self.service.get_distinct_languages(self.db_path)
            self.src_lang_combo.addItems(srcs)
            self.tgt_lang_combo.addItems(tgts)
        except Exception as e:
            logger.error(f"Failed to load language options: {e}", exc_info=True)

    def load_data(self):
        """加载数据"""
        if not self.db_path or not os.path.exists(self.db_path):
            logger.warning(f"Cannot load data: invalid db_path {self.db_path}")
            self._clear_all_data()
            return

        try:
            # 获取筛选条件
            filters = self._get_current_filters()

            # 获取总数
            self.total_count = self.service.count_entries(self.db_path, **filters)

            # 更新分页UI
            self._update_pagination_ui()

            # 获取当前页数据
            rows = self.service.query_entries(
                self.db_path,
                self.current_page,
                self.page_size,
                **filters
            )

            # 填充表格
            self._populate_table(rows)

        except Exception as e:
            logger.error(f"Failed to load data: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                _("Error"),
                _("Failed to load data: {error}").format(error=str(e))
            )

    def _get_current_filters(self):
        """获取当前筛选条件"""
        return {
            'source_key': (
                self.source_combo.currentText()
                if self.source_combo.currentData() != "All"
                else None
            ),
            'src_lang': (
                self.src_lang_combo.currentText()
                if self.src_lang_combo.currentData() != "All"
                else None
            ),
            'tgt_lang': (
                self.tgt_lang_combo.currentText()
                if self.tgt_lang_combo.currentData() != "All"
                else None
            ),
            'search_term': self.search_edit.text().strip()
        }

    def _update_pagination_ui(self):
        """更新分页UI状态"""
        # 更新总数标签
        self.total_label.setText(_("Total: {count}").format(count=self.total_count))

        # 计算总页数
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)

        # 确保当前页在有效范围内
        if self.current_page > total_pages:
            self.current_page = total_pages

        # 更新页码标签
        self.page_label.setText(
            _("Page {current} / {total}").format(
                current=self.current_page,
                total=total_pages
            )
        )

        # 更新按钮状态
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < total_pages)

    def _populate_table(self, rows):
        """填充表格数据"""
        # 阻止信号防止触发cellChanged
        self.table.blockSignals(True)

        try:
            self.table.setRowCount(0)
            self.table.setRowCount(len(rows))

            for i, row in enumerate(rows):
                self._populate_table_row(i, row)

        finally:
            self.table.blockSignals(False)

    def _populate_table_row(self, row_index, row_data):
        """填充单行数据"""
        # ID列
        self.table.setItem(
            row_index,
            self.COLUMN_ID,
            QTableWidgetItem(str(row_data['id']))
        )

        # 源文本
        src_item = QTableWidgetItem(row_data['source_text'])
        src_item.setFlags(src_item.flags() & ~Qt.ItemIsEditable)
        src_item.setToolTip(row_data['source_text'])
        self.table.setItem(row_index, self.COLUMN_SOURCE, src_item)

        # 目标文本
        tgt_item = QTableWidgetItem(row_data['target_text'])
        if self.mode == 'glossary':
            tgt_item.setFlags(tgt_item.flags() & ~Qt.ItemIsEditable)
        tgt_item.setToolTip(row_data['target_text'])
        self.table.setItem(row_index, self.COLUMN_TARGET, tgt_item)

        # 元数据列
        self.table.setItem(
            row_index,
            self.COLUMN_SRC_LANG,
            QTableWidgetItem(row_data['source_lang'])
        )
        self.table.setItem(
            row_index,
            self.COLUMN_TGT_LANG,
            QTableWidgetItem(row_data['target_lang'])
        )
        self.table.setItem(
            row_index,
            self.COLUMN_SOURCE_FILE,
            QTableWidgetItem(row_data['source_manifest_key'])
        )
        from PySide6.QtGui import QColor
        read_only_bg = QColor("#EFEFEF")

        read_only_cols = [
            self.COLUMN_ID,
            self.COLUMN_SOURCE,
            self.COLUMN_SRC_LANG,
            self.COLUMN_TGT_LANG,
            self.COLUMN_SOURCE_FILE
        ]

        if self.mode == 'glossary':
            read_only_cols.append(self.COLUMN_TARGET)

        for col in read_only_cols:
            item = self.table.item(row_index, col)
            if item:
                item.setBackground(read_only_bg)

    def on_cell_changed(self, row, column):
        if column != self.COLUMN_TARGET or self.mode != 'tm':
            return

        try:
            new_text = self.table.item(row, column).text()
            entry_id = int(self.table.item(row, self.COLUMN_ID).text())

            success = self.service.update_entry_target(self.db_path, entry_id, new_text)

            if success:
                self.data_updated.emit()
                logger.info(f"Updated entry {entry_id} successfully")
            else:
                raise Exception("Service returned False")

        except Exception as e:
            logger.error(f"Failed to update entry: {e}", exc_info=True)
            QMessageBox.warning(self, _("Error"), _("Failed to update entry."))
            self.load_data()  # 刷新回滚

    def show_context_menu(self, pos):
        """右键菜单"""
        item = self.table.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        delete_action = QAction(_("Delete Entry"), self)
        delete_action.triggered.connect(self.delete_selected_entry)
        menu.addAction(delete_action)
        menu.exec(QCursor.pos())

    def delete_selected_entry(self):
        row = self.table.currentRow()
        if row == -1:
            return

        try:
            entry_id = int(self.table.item(row, self.COLUMN_ID).text())
            src_text = self.table.item(row, self.COLUMN_SOURCE).text()

            # 确认删除
            reply = QMessageBox.question(
                self,
                _("Confirm Delete"),
                _("Are you sure you want to delete this entry?\n\n{src}").format(
                    src=src_text[:50]
                ),
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                success = self.service.delete_entry_by_id(self.db_path, entry_id)

                if success:
                    self.data_updated.emit()
                    logger.info(f"Deleted entry {entry_id} successfully")
                    self.load_data()
                else:
                    raise Exception("Service returned False")

        except Exception as e:
            logger.error(f"Failed to delete entry: {e}", exc_info=True)
            QMessageBox.critical(self, _("Error"), _("Failed to delete entry."))

    def on_search(self):
        self.current_page = 1
        self.load_data()

    def reset_filters(self):
        self.search_edit.clear()
        self.source_combo.setCurrentIndex(0)
        self.src_lang_combo.setCurrentIndex(0)
        self.tgt_lang_combo.setCurrentIndex(0)
        self.on_search()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def next_page(self):
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_data()