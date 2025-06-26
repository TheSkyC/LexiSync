# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QTreeView,
    QProgressBar, QSizePolicy, QHeaderView, QScrollArea, QWidget, QFrame,
    QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, QModelIndex, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QStandardItemModel, QStandardItem, QBrush, QColor, QPainter, QFont
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
        self.statistics['total_items'] = total_items
        self.statistics['translated_count'] = 0
        self.statistics['untranslated_count'] = 0
        self.statistics['reviewed_count'] = 0
        self.statistics['ignored_count'] = 0
        self.statistics['warning_count'] = 0
        self.statistics['minor_warning_count'] = 0
        self.statistics['warnings_by_type'] = {wt: [] for wt in WarningType}
        self.statistics['source_char_count'] = 0
        self.statistics['translation_char_count'] = 0
        time.sleep(0.1)

        for i, ts_obj in enumerate(self.translatable_objects):
            if (i + 1) % (total_items // 20 or 1) == 0:
                self.progress_updated.emit(int(10 + 70 * (i / total_items)),
                                           _("Processing item {i}/{total}...").format(i=i + 1, total=total_items))

            if ts_obj.is_ignored:
                self.statistics['ignored_count'] += 1
            elif ts_obj.translation.strip():
                self.statistics['translated_count'] += 1
                if ts_obj.is_reviewed:
                    self.statistics['reviewed_count'] += 1
            else:
                self.statistics['untranslated_count'] += 1

            has_major_warning = ts_obj.warnings and not ts_obj.is_warning_ignored
            has_minor_warning = ts_obj.minor_warnings and not ts_obj.is_warning_ignored

            if has_major_warning:
                self.statistics['warning_count'] += 1
                for wt, msg in ts_obj.warnings:
                    if ts_obj not in self.statistics['warnings_by_type'][wt]:
                        self.statistics['warnings_by_type'][wt].append(ts_obj)

            if has_minor_warning:
                if not has_major_warning:
                    self.statistics['minor_warning_count'] += 1
                for wt, msg in ts_obj.minor_warnings:
                    if ts_obj not in self.statistics['warnings_by_type'][wt]:
                        self.statistics['warnings_by_type'][wt].append(ts_obj)

            self.statistics['source_char_count'] += len(ts_obj.original_semantic)
            self.statistics['translation_char_count'] += len(ts_obj.translation)

        time.sleep(0.1)
        self.progress_updated.emit(90, _("Finalizing..."))
        time.sleep(0.1)
        self.calculation_finished.emit(self.statistics)


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
        self.setMinimumSize(900, 700)
        self.setModal(False)

        self.setStyleSheet("""
            QDialog { background-color: #F5F5F5; }
            QLabel { font-size: 13px; }
            QPushButton { font-size: 13px; padding: 6px 12px; }
            QSplitter::handle { background-color: #E0E0E0; border: 1px solid #D0D0D0; }
            QSplitter::handle:hover { background-color: #BDBDBD; }
            QSplitter::handle:pressed { background-color: #007BFF; }
            QFrame#container { background-color: white; border: 1px solid #D0D0D0; border-radius: 8px; }
            QTreeView, QScrollArea { border: none; background-color: white; }
            QTreeView::item { padding: 3px; }
            QTreeView::item:selected { background-color: #E0E8F0; }
        """)

        self.setup_ui()
        QTimer.singleShot(100, self.start_calculation)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter, 1)

        issues_container = QFrame()
        issues_container.setObjectName("container")
        issues_layout = QVBoxLayout(issues_container)
        issues_layout.setContentsMargins(1, 1, 1, 1)
        self.issues_tree_view = QTreeView()
        self.issues_tree_view.setHeaderHidden(True)
        self.issues_tree_view.doubleClicked.connect(self.on_issue_double_clicked)
        self.issues_tree_view.setAlternatingRowColors(True)
        issues_layout.addWidget(self.issues_tree_view)
        main_splitter.addWidget(issues_container)

        right_panel_widget = QWidget()
        right_panel_layout = QVBoxLayout(right_panel_widget)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_splitter = QSplitter(Qt.Vertical)
        right_panel_layout.addWidget(right_splitter)

        chart_container = QFrame()
        chart_container.setObjectName("container")
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(10, 10, 10, 10)
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        chart_layout.addWidget(self.chart_view)
        right_splitter.addWidget(chart_container)

        metrics_container = QFrame()
        metrics_container.setObjectName("container")
        metrics_container_layout = QVBoxLayout(metrics_container)
        metrics_container_layout.setContentsMargins(10, 10, 10, 10)
        metrics_scroll_area = QScrollArea()
        metrics_scroll_area.setWidgetResizable(True)
        metrics_widget = QWidget()
        self.metrics_layout = QGridLayout(metrics_widget)
        self.metrics_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.metrics_layout.setVerticalSpacing(8)
        self.metrics_layout.setHorizontalSpacing(15)
        metrics_scroll_area.setWidget(metrics_widget)
        metrics_container_layout.addWidget(metrics_scroll_area)
        right_splitter.addWidget(metrics_container)

        main_splitter.addWidget(right_panel_widget)

        self.progress_bar = AnimatedProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton(_("Refresh Data"))
        self.refresh_button.clicked.connect(self.start_calculation)
        button_layout.addWidget(self.refresh_button)
        button_layout.addStretch(1)
        self.close_button = QPushButton(_("Close"))
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

        main_splitter.setSizes([550, 300])
        right_splitter.setSizes([200, 450])

    def start_calculation(self):
        self.refresh_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.set_animated_value(0)

        self.clear_metrics_display()
        if hasattr(self, 'issues_model'): self.issues_model.clear()
        if self.chart_view.chart(): self.chart_view.chart().removeAllSeries()

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

    def add_simple_metric(self, label_text, value_text):
        label = QLabel(f"<b>{label_text}</b>")
        value = QLabel(str(value_text))
        value.setAlignment(Qt.AlignRight)
        self.metrics_layout.addWidget(label, self.metrics_row_index, 0)
        self.metrics_layout.addWidget(value, self.metrics_row_index, 1)
        self.metrics_row_index += 1

    def add_metric_with_progress(self, label_text, value_text, percentage_float, progress_color_hex):
        label = QLabel(f"<b>{label_text}</b>")
        value = QLabel(str(value_text))
        value.setAlignment(Qt.AlignRight)
        self.metrics_layout.addWidget(label, self.metrics_row_index, 0)
        self.metrics_layout.addWidget(value, self.metrics_row_index, 1)
        self.metrics_row_index += 1

        progress_bar = AnimatedProgressBar()
        progress_bar.set_animated_value(int(percentage_float * 100))
        progress_bar.setTextVisible(False)
        progress_bar.setFixedHeight(8)
        progress_bar.setMinimumWidth(150)
        progress_bar.setStyleSheet(f"""
            QProgressBar {{ border: none; border-radius: 4px; background-color: #E0E0E0; }}
            QProgressBar::chunk {{ background-color: {progress_color_hex}; border-radius: 4px; }}
        """)
        self.metrics_layout.addWidget(progress_bar, self.metrics_row_index, 0, 1, 2)
        self.metrics_row_index += 1

    def add_separator_line(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #E0E0E0;")
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

        total = stats_data.get('total_items', 0)
        self.clear_metrics_display()

        self.add_simple_metric(_("Total Items:"), f"<b>{total}</b>")
        self.add_separator_line()

        translated = stats_data.get('translated_count', 0)
        translated_p = translated / total if total else 0
        self.add_metric_with_progress(_("Translated:"), f"{translated} ({translated_p:.1%})", translated_p, "#4CAF50")

        untranslated = stats_data.get('untranslated_count', 0)
        untranslated_p = untranslated / total if total else 0
        self.add_metric_with_progress(_("Untranslated:"), f"{untranslated} ({untranslated_p:.1%})", untranslated_p,
                                      "#F44336")

        ignored = stats_data.get('ignored_count', 0)
        ignored_p = ignored / total if total else 0
        self.add_metric_with_progress(_("Ignored:"), f"{ignored} ({ignored_p:.1%})", ignored_p, "#9E9E9E")

        self.add_separator_line()

        reviewed = stats_data.get('reviewed_count', 0)
        reviewed_p_total = reviewed / total if total else 0
        self.add_metric_with_progress(_("Reviewed (of total):"), f"{reviewed} ({reviewed_p_total:.1%})",
                                      reviewed_p_total, "#4CAF50")
        reviewed_p_translated = reviewed / translated if translated else 0
        self.add_metric_with_progress(_("Reviewed (of translated):"), f"{reviewed} ({reviewed_p_translated:.1%})",
                                      reviewed_p_translated, "#2196F3")

        warning_count = stats_data.get('warning_count', 0) + stats_data.get('minor_warning_count', 0)
        warning_p = warning_count / total if total else 0
        self.add_metric_with_progress(_("Items with Warnings:"), f"{warning_count} ({warning_p:.1%})", warning_p,
                                      "#FF9800")

        self.add_separator_line()

        self.add_simple_metric(_("Source Characters:"), f"{stats_data.get('source_char_count', 0):,}")
        self.add_simple_metric(_("Translation Characters:"), f"{stats_data.get('translation_char_count', 0):,}")

        self.metrics_layout.setRowStretch(self.metrics_row_index, 1)

        series = QHorizontalStackedBarSeries()
        series.setLabelsVisible(True)
        series.setLabelsFormat("@value")

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
        chart.setTitle(_("Translation Progress"))
        chart.setAnimationOptions(QChart.AllAnimations)
        chart.setAnimationDuration(500)
        chart.setAnimationEasingCurve(QEasingCurve.OutCubic)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.setBackgroundVisible(False)

        axis_y = QBarCategoryAxis()
        axis_y.append([""])
        axis_y.setVisible(False)
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        axis_x = QValueAxis()
        axis_x.setRange(0, total if total > 0 else 1)
        axis_x.setLabelFormat("%d")
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        self.chart_view.setChart(chart)

        self.issues_model = QStandardItemModel()
        self.issues_model.setHorizontalHeaderLabels([_('Issue Description')])
        self.issues_tree_view.setModel(self.issues_model)
        self.issues_tree_view.header().setStretchLastSection(True)

        warnings_by_type = stats_data.get('warnings_by_type', {})
        for warning_type, ts_obj_list in sorted(warnings_by_type.items(), key=lambda item: item[0].name):
            if ts_obj_list:
                type_display_text = warning_type.get_display_text()
                category_item = QStandardItem(f"{type_display_text} ({len(ts_obj_list)})")
                category_item.setEditable(False)
                category_item.setData(warning_type, Qt.UserRole + 1)
                category_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                self.issues_model.appendRow(category_item)

                for ts_obj in ts_obj_list:
                    summary = ts_obj.original_semantic.replace("\n", " ").strip()
                    if len(summary) > 80: summary = summary[:77] + "..."
                    line_info = f" (Line: {ts_obj.line_num_in_file})" if ts_obj.line_num_in_file else ""

                    specific_msg = "Unknown warning"
                    found_msg = next((msg for wt, msg in ts_obj.warnings if wt == warning_type), None)
                    if not found_msg:
                        found_msg = next((msg for wt, msg in ts_obj.minor_warnings if wt == warning_type), None)
                    if found_msg:
                        specific_msg = found_msg

                    issue_text_line1 = f"{summary}{line_info}"
                    issue_item_line1 = QStandardItem(issue_text_line1)
                    issue_item_line1.setData(ts_obj.id, Qt.UserRole)
                    issue_item_line1.setEditable(False)
                    issue_item_line1.setToolTip(
                        f"Original: {ts_obj.original_semantic}\n\n{_('Double-click to locate.')}")

                    issue_text_line2 = f"  └ {specific_msg}"
                    issue_item_line2 = QStandardItem(issue_text_line2)
                    issue_item_line2.setData(ts_obj.id, Qt.UserRole)
                    issue_item_line2.setEditable(False)
                    issue_item_line2.setForeground(QColor("gray"))

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