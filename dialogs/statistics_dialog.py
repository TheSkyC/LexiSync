# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QTreeView,
    QProgressBar, QSizePolicy, QHeaderView, QScrollArea, QWidget, QFrame,
    QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, QModelIndex, QPropertyAnimation, QEasingCurve, QTimer, QMargins
from PySide6.QtGui import QStandardItemModel, QStandardItem, QBrush, QColor, QPainter, QFont, QPalette
from PySide6.QtCharts import QChart, QChartView, QHorizontalStackedBarSeries, QBarSet, QBarCategoryAxis, QValueAxis

from utils.localization import _
from utils.enums import WarningType
import time


class StatisticsCalculationThread(QThread):
    progress_updated = Signal(int, str)
    calculation_finished = Signal(dict)

    def __init__(self, translatable_objects, parent=None):
        super().__init__(parent)
        self.translatable_objects = translatable_objects
        self.statistics = {}

    def run(self):
        total_items = len(self.translatable_objects)
        if total_items == 0:
            self.calculation_finished.emit({})
            return

        self.progress_updated.emit(10, _("Calculating core metrics..."))
        self._initialize_statistics(total_items)
        time.sleep(0.1)

        self._process_translatable_objects(total_items)

        time.sleep(0.1)
        self.progress_updated.emit(90, _("Finalizing..."))
        time.sleep(0.1)
        self.calculation_finished.emit(self.statistics)

    def _initialize_statistics(self, total_items):
        self.statistics = {
            'total_items': total_items,
            'translated_count': 0,
            'untranslated_count': 0,
            'reviewed_count': 0,
            'ignored_count': 0,
            'warning_count': 0,
            'minor_warning_count': 0,
            'warnings_by_type': {wt: [] for wt in WarningType},
            'source_char_count': 0,
            'translation_char_count': 0
        }

    def _process_translatable_objects(self, total_items):
        for i, ts_obj in enumerate(self.translatable_objects):
            if (i + 1) % (total_items // 20 or 1) == 0:
                progress = int(10 + 70 * (i / total_items))
                status = _("Processing item {i}/{total}...").format(i=i + 1, total=total_items)
                self.progress_updated.emit(progress, status)

            self._process_single_object(ts_obj)

    def _process_single_object(self, ts_obj):
        if ts_obj.is_ignored:
            self.statistics['ignored_count'] += 1
        elif ts_obj.translation.strip():
            self.statistics['translated_count'] += 1
            if ts_obj.is_reviewed:
                self.statistics['reviewed_count'] += 1
        else:
            self.statistics['untranslated_count'] += 1

        self._process_warnings(ts_obj)
        self.statistics['source_char_count'] += len(ts_obj.original_semantic)
        self.statistics['translation_char_count'] += len(ts_obj.translation)

    def _process_warnings(self, ts_obj):
        has_major_warning = ts_obj.warnings and not ts_obj.is_warning_ignored
        has_minor_warning = ts_obj.minor_warnings and not ts_obj.is_warning_ignored

        if has_major_warning:
            self.statistics['warning_count'] += 1
            self._add_warnings_to_stats(ts_obj, ts_obj.warnings)

        if has_minor_warning:
            if not has_major_warning:
                self.statistics['minor_warning_count'] += 1
            self._add_warnings_to_stats(ts_obj, ts_obj.minor_warnings)

    def _add_warnings_to_stats(self, ts_obj, warnings):
        for wt, msg in warnings:
            if ts_obj not in self.statistics['warnings_by_type'][wt]:
                self.statistics['warnings_by_type'][wt].append(ts_obj)


class AnimatedProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(400)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)

    def set_animated_value(self, value):
        self.animation.stop()
        self.animation.setStartValue(self.value())
        self.animation.setEndValue(value)
        self.animation.start()


class StatisticsDialog(QDialog):
    locate_item_signal = Signal(str)

    def __init__(self, parent, translatable_objects):
        super().__init__(parent)
        self.translatable_objects = translatable_objects
        self.statistics_data = {}
        self.metrics_row_index = 0
        self.calc_thread = None

        self.setWindowTitle(_("Project Statistics"))
        self.setMinimumSize(1000, 750)
        self.setModal(False)

        self._setup_styles()
        self.setup_ui()
        QTimer.singleShot(100, self.start_calculation)

    def _setup_styles(self):
        self.setStyleSheet("""
            QDialog { 
                background-color: #FAFAFA; 
                font-family: "Segoe UI", Arial, sans-serif;
            }

            QLabel { 
                font-size: 13px; 
                color: #333333;
            }

            QPushButton { 
                font-size: 13px; 
                padding: 8px 16px; 
                border: 1px solid #CCCCCC;
                border-radius: 6px;
                background-color: #FFFFFF;
                color: #333333;
            }
            QPushButton:hover { 
                background-color: #F0F8FF; 
                border-color: #007BFF;
            }
            QPushButton:pressed { 
                background-color: #E6F3FF; 
            }
            QPushButton:disabled { 
                background-color: #F5F5F5; 
                color: #999999;
            }

            QSplitter::handle { 
                background-color: #E8E8E8; 
                border: 1px solid #DDDDDD; 
                border-radius: 2px;
            }
            QSplitter::handle:hover { 
                background-color: #D0D0D0; 
            }
            QSplitter::handle:pressed { 
                background-color: #007BFF; 
            }

            QFrame#container { 
                background-color: #FFFFFF; 
                border: 1px solid #E0E0E0; 
                border-radius: 10px;
                margin: 2px;
            }

            QScrollArea { 
                border: none; 
                background-color: transparent; 
            }

            QTreeView { 
                border: none; 
                background-color: #FFFFFF;
                alternate-background-color: #F8F9FA;
                selection-background-color: #E3F2FD;
                selection-color: #1976D2;
                outline: none;
            }
            QTreeView::item { 
                padding: 6px 4px; 
                border: none;
                min-height: 18px;
            }
            QTreeView::item:selected { 
                background-color: #E3F2FD; 
                color: #1976D2;
            }
            QTreeView::item:selected:active { 
                background-color: #BBDEFB; 
                color: #0D47A1;
            }
            QTreeView::item:selected:!active { 
                background-color: #F0F7FF; 
                color: #1976D2;
            }
            QTreeView::item:hover:!selected { 
                background-color: #F5F5F5; 
            }

            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {
                border-image: none;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTYgNEwxMCA4TDYgMTJWNFoiIGZpbGw9IiM2NjY2NjYiLz4KPC9zdmc+);
            }

            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings {
                border-image: none;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQgNkw4IDEwTDEyIDZINFoiIGZpbGw9IiM2NjY2NjYiLz4KPC9zdmc+);
            }
        """)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Main splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter, 1)

        # Left panel - Issues tree
        self._setup_issues_panel(main_splitter)

        # Right panel - Charts and metrics
        self._setup_right_panel(main_splitter)

        # Progress bar
        self.progress_bar = AnimatedProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                background-color: #F5F5F5;
                text-align: center;
                height: 16px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #81C784);
                border-radius: 6px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # Buttons
        self._setup_buttons(main_layout)

        # Set initial splitter sizes
        main_splitter.setSizes([600, 400])

    def _setup_issues_panel(self, parent_splitter):
        issues_container = QFrame()
        issues_container.setObjectName("container")
        issues_layout = QVBoxLayout(issues_container)
        issues_layout.setContentsMargins(12, 12, 12, 12)

        # Issues title
        issues_title = QLabel(_("Issues & Warnings"))
        issues_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        issues_title.setStyleSheet("color: #333333; margin-bottom: 8px;")
        issues_layout.addWidget(issues_title)

        self.issues_tree_view = QTreeView()
        self.issues_tree_view.setHeaderHidden(True)
        self.issues_tree_view.doubleClicked.connect(self.on_issue_double_clicked)
        self.issues_tree_view.setAlternatingRowColors(True)
        self.issues_tree_view.setRootIsDecorated(True)
        self.issues_tree_view.setIndentation(20)
        issues_layout.addWidget(self.issues_tree_view)

        parent_splitter.addWidget(issues_container)

    def _setup_right_panel(self, parent_splitter):
        right_panel_widget = QWidget()
        right_panel_layout = QVBoxLayout(right_panel_widget)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(8)

        right_splitter = QSplitter(Qt.Vertical)
        right_panel_layout.addWidget(right_splitter)

        # Chart panel
        self._setup_chart_panel(right_splitter)

        # Metrics panel
        self._setup_metrics_panel(right_splitter)

        right_splitter.setSizes([180, 520])
        parent_splitter.addWidget(right_panel_widget)

    def _setup_chart_panel(self, parent_splitter):
        chart_container = QFrame()
        chart_container.setObjectName("container")
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(12, 12, 12, 12)

        chart_title = QLabel(_("Translation Progress"))
        chart_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        chart_title.setAlignment(Qt.AlignCenter)
        chart_title.setStyleSheet("color: #333333; margin-bottom: 8px;")
        chart_layout.addWidget(chart_title)

        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setStyleSheet("border: none; background: transparent;")
        chart_layout.addWidget(self.chart_view)

        parent_splitter.addWidget(chart_container)

    def _setup_metrics_panel(self, parent_splitter):
        metrics_container = QFrame()
        metrics_container.setObjectName("container")
        metrics_container_layout = QVBoxLayout(metrics_container)
        metrics_container_layout.setContentsMargins(12, 12, 12, 12)

        metrics_title = QLabel(_("Project Metrics"))
        metrics_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        metrics_title.setStyleSheet("color: #333333; margin-bottom: 12px;")
        metrics_container_layout.addWidget(metrics_title)

        metrics_scroll_area = QScrollArea()
        metrics_scroll_area.setWidgetResizable(True)
        metrics_scroll_area.setStyleSheet("QScrollArea { background: transparent; }")

        metrics_widget = QWidget()
        metrics_widget.setStyleSheet("background: transparent;")
        self.metrics_layout = QGridLayout(metrics_widget)
        self.metrics_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.metrics_layout.setVerticalSpacing(10)
        self.metrics_layout.setHorizontalSpacing(20)
        self.metrics_layout.setColumnStretch(0, 1)
        self.metrics_layout.setColumnStretch(1, 0)

        metrics_scroll_area.setWidget(metrics_widget)
        metrics_container_layout.addWidget(metrics_scroll_area)

        parent_splitter.addWidget(metrics_container)

    def _setup_buttons(self, main_layout):
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.refresh_button = QPushButton(_("🔄 Refresh Data"))
        self.refresh_button.clicked.connect(self.start_calculation)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                background-color: #007BFF;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #0056B3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        button_layout.addWidget(self.refresh_button)

        button_layout.addStretch(1)

        self.close_button = QPushButton(_("Close"))
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)

        main_layout.addLayout(button_layout)

    def start_calculation(self):
        self.refresh_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.set_animated_value(0)

        self.clear_metrics_display()
        if hasattr(self, 'issues_model'):
            self.issues_model.clear()
        if self.chart_view.chart():
            self.chart_view.chart().removeAllSeries()

        self.calc_thread = StatisticsCalculationThread(self.translatable_objects, self)
        self.calc_thread.progress_updated.connect(self.update_progress)
        self.calc_thread.calculation_finished.connect(self.display_statistics)
        self.calc_thread.start()

    def update_progress(self, value, status_text):
        self.progress_bar.set_animated_value(value)
        self.setWindowTitle(f"{_('Project Statistics')} - {status_text}")

    def clear_metrics_display(self):
        while self.metrics_layout.count():
            item = self.metrics_layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()
        self.metrics_row_index = 0

    def add_simple_metric(self, label_text, value_text, is_header=False):
        label = QLabel(label_text)
        value = QLabel(str(value_text))
        value.setAlignment(Qt.AlignRight)

        if is_header:
            font = QFont("Segoe UI", 14, QFont.Weight.Bold)
            label.setFont(font)
            value.setFont(font)
            label.setStyleSheet("color: #1976D2;")
            value.setStyleSheet("color: #1976D2;")
        else:
            label.setStyleSheet("font-weight: bold; color: #555555;")
            value.setStyleSheet("color: #333333;")

        self.metrics_layout.addWidget(label, self.metrics_row_index, 0)
        self.metrics_layout.addWidget(value, self.metrics_row_index, 1)
        self.metrics_row_index += 1

    def add_metric_with_progress(self, label_text, value_text, percentage_float, progress_color_hex):
        label = QLabel(label_text)
        value = QLabel(str(value_text))
        value.setAlignment(Qt.AlignRight)
        label.setStyleSheet("font-weight: bold; color: #555555;")
        value.setStyleSheet("color: #333333;")

        self.metrics_layout.addWidget(label, self.metrics_row_index, 0)
        self.metrics_layout.addWidget(value, self.metrics_row_index, 1)
        self.metrics_row_index += 1

        progress_bar = AnimatedProgressBar()
        progress_bar.set_animated_value(int(percentage_float * 100))
        progress_bar.setTextVisible(False)
        progress_bar.setFixedHeight(10)
        progress_bar.setMinimumWidth(180)
        progress_bar.setStyleSheet(f"""
            QProgressBar {{ 
                border: 1px solid #E0E0E0; 
                border-radius: 5px; 
                background-color: #F8F8F8; 
            }}
            QProgressBar::chunk {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {progress_color_hex}, stop:1 {self._lighten_color(progress_color_hex)});
                border-radius: 4px; 
            }}
        """)
        self.metrics_layout.addWidget(progress_bar, self.metrics_row_index, 0, 1, 2)
        self.metrics_row_index += 1

    def _lighten_color(self, hex_color, factor=0.3):
        try:
            color = QColor(hex_color)
            h, s, v, a = color.getHsv()
            v = min(255, int(v + (255 - v) * factor))
            return QColor.fromHsv(h, s, v, a).name()
        except:
            return hex_color

    def add_separator_line(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setStyleSheet("background-color: #E8E8E8; margin: 8px 0px;")
        line.setFixedHeight(1)
        self.metrics_layout.addWidget(line, self.metrics_row_index, 0, 1, 2)
        self.metrics_row_index += 1

    def display_statistics(self, stats_data):
        self.statistics_data = stats_data
        self.progress_bar.set_animated_value(100)
        QTimer.singleShot(500, lambda: self.progress_bar.setVisible(False))
        self.refresh_button.setEnabled(True)
        self.setWindowTitle(_("Project Statistics"))

        if not stats_data:
            self.add_simple_metric(_("Error:"), _("No data to display."))
            return

        self._display_metrics(stats_data)
        self._display_chart(stats_data)
        self._display_issues_tree(stats_data)

    def _display_metrics(self, stats_data):
        total = stats_data.get('total_items', 0)
        self.clear_metrics_display()

        # Main total
        self.add_simple_metric(_("Total Items"), f"{total}", is_header=True)
        self.add_separator_line()

        # Translation status
        translated = stats_data.get('translated_count', 0)
        translated_p = translated / total if total else 0
        self.add_metric_with_progress(_("Translated"), f"{translated} ({translated_p:.1%})",
                                      translated_p, "#4CAF50")

        untranslated = stats_data.get('untranslated_count', 0)
        untranslated_p = untranslated / total if total else 0
        self.add_metric_with_progress(_("Untranslated"), f"{untranslated} ({untranslated_p:.1%})",
                                      untranslated_p, "#F44336")

        ignored = stats_data.get('ignored_count', 0)
        ignored_p = ignored / total if total else 0
        self.add_metric_with_progress(_("Ignored"), f"{ignored} ({ignored_p:.1%})",
                                      ignored_p, "#9E9E9E")

        self.add_separator_line()

        # Review status
        reviewed = stats_data.get('reviewed_count', 0)
        reviewed_p_total = reviewed / total if total else 0
        self.add_metric_with_progress(_("Reviewed (of total)"), f"{reviewed} ({reviewed_p_total:.1%})",
                                      reviewed_p_total, "#4CAF50")

        reviewed_p_translated = reviewed / translated if translated else 0
        self.add_metric_with_progress(_("Reviewed (of translated)"), f"{reviewed} ({reviewed_p_translated:.1%})",
                                      reviewed_p_translated, "#2196F3")

        # Warnings
        warning_count = stats_data.get('warning_count', 0) + stats_data.get('minor_warning_count', 0)
        warning_p = warning_count / total if total else 0
        self.add_metric_with_progress(_("Items with Warnings"), f"{warning_count} ({warning_p:.1%})",
                                      warning_p, "#FF9800")

        self.add_separator_line()

        # Character counts
        source_chars = stats_data.get('source_char_count', 0)
        translation_chars = stats_data.get('translation_char_count', 0)
        self.add_simple_metric(_("Source Characters"), f"{source_chars:,}")
        self.add_simple_metric(_("Translation Characters"), f"{translation_chars:,}")

        # Expansion ratio
        if source_chars > 0:
            expansion_ratio = translation_chars / source_chars
            self.add_simple_metric(_("Expansion Ratio"), f"{expansion_ratio:.2f}x")

        self.metrics_layout.setRowStretch(self.metrics_row_index, 1)

    def _display_chart(self, stats_data):
        translated = stats_data.get('translated_count', 0)
        untranslated = stats_data.get('untranslated_count', 0)
        ignored = stats_data.get('ignored_count', 0)
        total = stats_data.get('total_items', 0)

        series = QHorizontalStackedBarSeries()
        series.setLabelsVisible(True)
        series.setLabelsFormat("@value")

        # Create bar sets with modern colors
        set_translated = QBarSet(_("Translated"))
        set_translated << translated
        set_translated.setColor(QColor("#4CAF50"))
        series.append(set_translated)

        set_untranslated = QBarSet(_("Untranslated"))
        set_untranslated << untranslated
        set_untranslated.setColor(QColor("#F44336"))
        series.append(set_untranslated)

        set_ignored = QBarSet(_("Ignored"))
        set_ignored << ignored
        set_ignored.setColor(QColor("#9E9E9E"))
        series.append(set_ignored)

        chart = QChart()
        chart.addSeries(series)
        chart.setAnimationOptions(QChart.AllAnimations)
        chart.setAnimationDuration(800)
        chart.setAnimationEasingCurve(QEasingCurve.OutCubic)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.setBackgroundVisible(False)
        chart.setMargins(QMargins(0, 0, 0, 0))

        # Setup axes
        axis_y = QBarCategoryAxis()
        axis_y.append([""])
        axis_y.setVisible(False)
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        axis_x = QValueAxis()
        axis_x.setRange(0, total if total > 0 else 1)
        axis_x.setLabelFormat("%d")
        axis_x.setGridLineVisible(False)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        self.chart_view.setChart(chart)

    def _display_issues_tree(self, stats_data):
        self.issues_model = QStandardItemModel()
        self.issues_model.setHorizontalHeaderLabels([_('Issue Description')])
        self.issues_tree_view.setModel(self.issues_model)
        self.issues_tree_view.header().setStretchLastSection(True)

        warnings_by_type = stats_data.get('warnings_by_type', {})
        total_issues = sum(len(ts_obj_list) for ts_obj_list in warnings_by_type.values())

        if total_issues == 0:
            no_issues_item = QStandardItem(_("✅ No issues found"))
            no_issues_item.setEditable(False)
            no_issues_item.setForeground(QColor("#4CAF50"))
            font = QFont("Segoe UI", 11, QFont.Weight.Bold)
            no_issues_item.setFont(font)
            self.issues_model.appendRow(no_issues_item)
            return

        for warning_type, ts_obj_list in sorted(warnings_by_type.items(), key=lambda item: item[0].name):
            if ts_obj_list:
                self._add_warning_category(warning_type, ts_obj_list)

        # Expand all categories
        # self.issues_tree_view.expandAll()

    def _add_warning_category(self, warning_type, ts_obj_list):
        type_display_text = warning_type.get_display_text()
        category_item = QStandardItem(f"⚠️ {type_display_text} ({len(ts_obj_list)})")
        category_item.setEditable(False)
        category_item.setData(warning_type, Qt.UserRole + 1)
        category_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        category_item.setForeground(QColor("#FF9800"))
        self.issues_model.appendRow(category_item)

        for ts_obj in ts_obj_list:
            summary = ts_obj.original_semantic.replace("\n", " ").strip()
            if len(summary) > 80:
                summary = summary[:77] + "..."
            line_info = f" (Line: {ts_obj.line_num_in_file})" if ts_obj.line_num_in_file else ""
            specific_msg = "Unknown warning"
            found_msg = next((msg for wt, msg in ts_obj.warnings if wt == warning_type), None)
            if not found_msg:
                found_msg = next((msg for wt, msg in ts_obj.minor_warnings if wt == warning_type), None)
            if found_msg:
                specific_msg = found_msg
            issue_text_line1 = f"📄 {summary}{line_info}"
            issue_item_line1 = QStandardItem(issue_text_line1)
            issue_item_line1.setData(ts_obj.id, Qt.UserRole)
            issue_item_line1.setEditable(False)
            issue_item_line1.setToolTip(
                f"Original: {ts_obj.original_semantic}\n\n{_('Double-click to locate.')}")
            issue_item_line1.setForeground(QColor("#666666"))
            issue_text_line2 = f"  └ {specific_msg}"
            issue_item_line2 = QStandardItem(issue_text_line2)
            issue_item_line2.setData(ts_obj.id, Qt.UserRole)
            issue_item_line2.setEditable(False)
            issue_item_line2.setForeground(QColor("#999999"))
            issue_item_line2.setFont(QFont("Segoe UI", 9))

            category_item.appendRow([issue_item_line1])
            category_item.appendRow([issue_item_line2])

    def on_issue_double_clicked(self, index: QModelIndex):
        item = self.issues_model.itemFromIndex(index.siblingAtColumn(0))
        if item:
            item_id = item.data(Qt.UserRole)
            if item_id:
                self.locate_item_signal.emit(item_id)
                self.activateWindow()
                self.raise_()

    def closeEvent(self, event):
        if self.calc_thread and self.calc_thread.isRunning():
            self.calc_thread.requestInterruption()
            self.calc_thread.wait(500)
        super().closeEvent(event)