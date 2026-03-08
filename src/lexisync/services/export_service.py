# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import datetime
import json

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
import yaml

from lexisync.utils.localization import _
from lexisync.utils.path_utils import get_resource_path


def export_to_html(filepath, translatable_objects, app_instance):
    project_name = "LexiSync Project"
    source_lang = "Unknown"
    target_lang = "Unknown"

    if app_instance.is_project_mode:
        project_name = app_instance.project_config.get("name", project_name)
        source_lang = app_instance.project_config.get("source_language", "en")
        target_lang = app_instance.current_target_language
    else:
        source_lang = app_instance.source_language
        target_lang = app_instance.current_target_language

    # 统计数据
    total = len(translatable_objects)
    translated = len([ts for ts in translatable_objects if ts.translation.strip() and not ts.is_ignored])
    ignored = len([ts for ts in translatable_objects if ts.is_ignored])
    reviewed = len([ts for ts in translatable_objects if ts.is_reviewed])
    progress = int(translated / total * 100) if total > 0 else 0

    # 字段说明：
    #   status  : 'untranslated' | 'fuzzy' | 'translated' | 'reviewed' | 'ignored'
    #   lbl     : 本地化后的状态标签文字
    #   src     : 原文
    #   tgt     : 译文
    #   ctx     : 上下文 key（可选）
    #   cmt     : 注释（可选）
    #   plural  : 是否复数条目
    #   src_plural    : 复数原文（plural=True 时有效）
    #   plural_trans  : 复数译文列表（plural=True 时有效）
    rows_data = []
    for ts in translatable_objects:
        # 确定状态与标签
        if ts.is_ignored:
            status = "ignored"
            lbl = _("Ignored")
        elif ts.is_reviewed:
            status = "reviewed"
            lbl = _("Reviewed")
        elif ts.is_fuzzy:
            status = "fuzzy"
            lbl = _("Fuzzy")
        elif not ts.translation.strip():
            status = "untranslated"
            lbl = _("Untranslated")
        else:
            status = "translated"
            lbl = _("Translated")

        entry = {
            "status": status,
            "lbl": lbl,
            "src": ts.original_semantic,
            "tgt": ts.translation,
        }
        if ts.context:
            entry["ctx"] = ts.context
        if ts.comment or ts.po_comment:
            po_c = ts.po_comment if ts.po_comment else ""
            normal_c = ts.comment if ts.comment else ""
            full_comment = (po_c + "\n" + normal_c).strip()
            if full_comment:
                entry["cmt"] = full_comment
        if ts.is_plural:
            entry["plural"] = True
            entry["src_plural"] = ts.original_plural or ""
            # plural_translations 是 {idx: str} 的字典，转为列表
            if ts.plural_translations:
                max_idx = max(ts.plural_translations.keys()) if ts.plural_translations else 0
                entry["plural_trans"] = [ts.plural_translations.get(i, "") for i in range(max_idx + 1)]

        rows_data.append(entry)

    report_data_json = json.dumps(rows_data, ensure_ascii=False, separators=(",", ":"))
    template_path = get_resource_path("resources/templates/report_template.html")
    try:
        with open(template_path, encoding="utf-8") as f:
            template_content = f.read()

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # 将所有占位符加入到替换字典中
        replacements = {
            "{project_name}": str(project_name),
            "{source_lang}": str(source_lang),
            "{target_lang}": str(target_lang),
            "{export_date}": now_str,
            "{total}": str(total),
            "{progress}": str(progress),
            "{translated}": str(translated),
            "{reviewed}": str(reviewed),
            "{ignored}": str(ignored),
            "{version}": app_instance.config.get("version", "1.3.0"),
            # 数据注入
            "{report_data_json}": report_data_json,
            # 基础本地化标签
            "{lbl_source_lang}": _("Source Language"),
            "{lbl_target_lang}": _("Target Language"),
            "{lbl_export_date}": _("Export Date"),
            "{lbl_total_items}": _("Total Items"),
            "{lbl_translated}": _("Translated"),
            "{lbl_reviewed}": _("Reviewed"),
            "{lbl_ignored}": _("Ignored"),
            "{lbl_source_text}": _("Source Text"),
            "{lbl_translation}": _("Translation"),
            # 交互组件与状态本地化
            "{ph_search}": _("Search source, translation or comments..."),
            "{lbl_all}": _("All"),
            "{lbl_untranslated}": _("Untranslated"),
            "{lbl_fuzzy}": _("Fuzzy"),
            "{lbl_comment}": _("Comments"),
            "{lbl_context}": _("Context"),
            "{lbl_status}": _("Status"),
            "{lbl_toggle_theme}": _("Toggle Theme"),
            "{lbl_scroll_to_top}": _("Scroll to Top"),
            "{lbl_virtual}": _("Virtual"),
            "{lbl_pages}": _("Pages"),
            "{lbl_showing}": _("Showing"),
            "{lbl_of}": _("of"),
            "{lbl_entries}": _("entries"),
            "{lbl_no_entries}": _("No entries match the current filter."),
            "{lbl_singular}": _("Singular"),
            "{lbl_plural}": _("Plural"),
            "{lbl_form}": _("Form"),
            "{lbl_prev}": _("Prev"),
            "{lbl_next}": _("Next"),
            "{lbl_rows}": _("Rows"),
            "{lbl_page}": _("page"),
        }

        final_html = template_content
        for placeholder, value in replacements.items():
            final_html = final_html.replace(placeholder, value)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(final_html)

    except Exception as e:
        raise OSError(f"Failed to load or process HTML template: {e}") from e


def export_to_json(filepath, translatable_objects, displayed_ids_order=None, app_instance=None):
    items_to_export_data = []
    export_obj_list = []
    if displayed_ids_order and app_instance:
        obj_map = {obj.id: obj for obj in app_instance.translatable_objects}
        export_obj_list = [obj_map[ts_id] for ts_id in displayed_ids_order if ts_id in obj_map]
    elif app_instance:  # Fallback to all if no specific order/filter is provided
        export_obj_list = app_instance.translatable_objects
    else:
        export_obj_list = translatable_objects

    for ts_obj in export_obj_list:
        items_to_export_data.append(
            {
                "id": ts_obj.id,
                "string_type": ts_obj.string_type,
                "original_semantic": ts_obj.original_semantic,
                "translation": ts_obj.get_translation_for_storage_and_tm(),
                "comment": ts_obj.comment,
                "is_reviewed": ts_obj.is_reviewed,
                "is_ignored": ts_obj.is_ignored,
                "line_num_in_file": ts_obj.line_num_in_file,
                "original_raw": ts_obj.original_raw,
                "is_plural": ts_obj.is_plural,
                "original_plural": ts_obj.original_plural,
                "plural_translations": ts_obj.plural_translations,
            }
        )

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(items_to_export_data, f, indent=4, ensure_ascii=False)


def export_to_yaml(filepath, translatable_objects, displayed_ids_order=None, app_instance=None):
    items_to_export_data = []

    export_obj_list = []
    if displayed_ids_order and app_instance:
        obj_map = {obj.id: obj for obj in app_instance.translatable_objects}
        export_obj_list = [obj_map[ts_id] for ts_id in displayed_ids_order if ts_id in obj_map]
    elif app_instance:  # Fallback to all if no specific order/filter is provided
        export_obj_list = app_instance.translatable_objects
    else:
        export_obj_list = translatable_objects

    for ts_obj in export_obj_list:
        items_to_export_data.append(
            {
                "id": ts_obj.id,
                "string_type": ts_obj.string_type,
                "original_semantic": ts_obj.original_semantic,
                "translation": ts_obj.get_translation_for_storage_and_tm(),
                "comment": ts_obj.comment,
                "is_reviewed": ts_obj.is_reviewed,
                "is_ignored": ts_obj.is_ignored,
                "line_num_in_file": ts_obj.line_num_in_file,
                "original_raw": ts_obj.original_raw,
                "is_plural": ts_obj.is_plural,
                "original_plural": ts_obj.original_plural,
                "plural_translations": ts_obj.plural_translations,
            }
        )

    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(items_to_export_data, f, allow_unicode=True, sort_keys=False)


def export_qa_report(filepath, issues, project_name="LexiSync Project"):
    """
    生成带格式的 QA 报告
    issues: List of dicts {severity, file, line, source, translation, type, message, ignored}
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "QA Issues"

    # 定义样式
    header_fill = PatternFill(start_color="333333", end_color="333333", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    error_fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")  # 浅红
    warning_fill = PatternFill(start_color="FFFDE7", end_color="FFFDE7", fill_type="solid")  # 浅黄
    info_fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")  # 浅蓝

    headers = [
        _("Severity"),
        _("File"),
        _("Line/ID"),
        _("Source"),
        _("Translation"),
        _("Issue Type"),
        _("Description"),
        _("Status"),
    ]
    ws.append(headers)

    # 应用表头样式
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for issue in issues:
        row_data = [
            issue["severity"].upper(),
            issue["file"],
            issue["line"],
            issue["source"],
            issue["translation"],
            issue["type"],
            issue["message"],
            _("Ignored") if issue["ignored"] else _("Active"),
        ]
        ws.append(row_data)

        # 应用行样式
        last_row = ws.max_row
        fill = None
        if issue["severity"] == "error":
            fill = error_fill
        elif issue["severity"] == "warning":
            fill = warning_fill
        elif issue["severity"] == "info":
            fill = info_fill

        if fill:
            for cell in ws[last_row]:
                cell.fill = fill

    # 自动调整列宽
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                max_length = max(max_length, len(str(cell.value)))
            except Exception:
                pass
        adjusted_width = min(max_length + 2, 50)  # 最高50
        ws.column_dimensions[column_letter].width = adjusted_width

    wb.save(filepath)
