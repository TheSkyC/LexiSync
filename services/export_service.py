# services/export_service.py
import json
import yaml


def export_to_json(filepath, translatable_objects, displayed_ids_order=None, app_instance=None):
    items_to_export_data = []

    # Determine which items to export: displayed or all
    export_obj_list = []
    if displayed_ids_order and app_instance:
        obj_map = {obj.id: obj for obj in app_instance.translatable_objects}
        export_obj_list = [obj_map[ts_id] for ts_id in displayed_ids_order if ts_id in obj_map]
    elif app_instance:
        export_obj_list = app_instance.translatable_objects
    else:  # Fallback if app_instance not provided, export based on input list
        export_obj_list = translatable_objects

    for ts_obj in export_obj_list:
        items_to_export_data.append({
            "id": ts_obj.id,
            "string_type": ts_obj.string_type,
            "original_semantic": ts_obj.original_semantic,
            "translation": ts_obj.get_translation_for_storage_and_tm(),
            "comment": ts_obj.comment,
            "is_reviewed": ts_obj.is_reviewed,
            "is_ignored": ts_obj.is_ignored,
            "line_num_in_file": ts_obj.line_num_in_file,
            "original_raw": ts_obj.original_raw
        })

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(items_to_export_data, f, indent=4, ensure_ascii=False)


def export_to_yaml(filepath, translatable_objects, displayed_ids_order=None, app_instance=None):
    items_to_export_data = []

    export_obj_list = []
    if displayed_ids_order and app_instance:
        obj_map = {obj.id: obj for obj in app_instance.translatable_objects}
        export_obj_list = [obj_map[ts_id] for ts_id in displayed_ids_order if ts_id in obj_map]
    elif app_instance:
        export_obj_list = app_instance.translatable_objects
    else:
        export_obj_list = translatable_objects

    for ts_obj in export_obj_list:
        items_to_export_data.append({
            "id": ts_obj.id,
            "string_type": ts_obj.string_type,
            "original_semantic": ts_obj.original_semantic,
            "translation": ts_obj.get_translation_for_storage_and_tm(),
            "comment": ts_obj.comment,
            "is_reviewed": ts_obj.is_reviewed,
            "is_ignored": ts_obj.is_ignored,
            "line_num_in_file": ts_obj.line_num_in_file,
            "original_raw": ts_obj.original_raw
        })

    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(items_to_export_data, f, allow_unicode=True, sort_keys=False)