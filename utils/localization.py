# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import json
import os
from tkinter import messagebox

class LocalizationService:
    def __init__(self, lang_dir='lang', language='en_us'):
        self.lang_dir = lang_dir
        self.languages = {}
        self.current_lang_data = {}
        self.current_lang = None
        self._load_available_languages()
        self.set_language(language)

    def _load_available_languages(self):
        self.available_languages = {
            "en_us": "English",
            "zh_cn": "简体中文"
        }

    def get_available_languages(self):
        return self.available_languages

    def load_language(self, lang_code):
        if lang_code in self.languages:
            return self.languages[lang_code]

        filepath = os.path.join(self.lang_dir, f"{lang_code}.json")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.languages[lang_code] = json.load(f)
                return self.languages[lang_code]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load language file for '{lang_code}': {e}")
            if lang_code != 'en_us':
                return self.load_language('en_us')
            return {}

    def set_language(self, lang_code):
        data = self.load_language(lang_code)
        if data:
            self.current_lang_data = data
            self.current_lang = lang_code
        else:
            print(f"Fatal: Could not load any language data. Using keys as fallback.")
            self.current_lang_data = {}
            self.current_lang = lang_code

    def get(self, key, *args, **kwargs):
        keys = key.split('.')
        try:
            value = self.current_lang_data
            for k in keys:
                value = value[k]

            if args or kwargs:
                return value.format(*args, **kwargs)
            return value
        except KeyError:
            print(f"Warning: Translation key not found: '{key}'")
            return key
        except TypeError:
             print(f"Warning: Language data for '{self.current_lang}' is not a dictionary. Key: '{key}'")
             return key


class LocalizationManager:
    def __init__(self, app_instance):
        self.app = app_instance
        self.i18n = LocalizationService(language=self.app.config.get("language", "en_us"))
        self.get = self.i18n.get  # 创建别名

    def change_language(self):
        _ = self.get
        new_lang = self.app.selected_language.get()
        if new_lang != self.i18n.current_lang:
            self.i18n.set_language(new_lang)
            self.app.config["language"] = new_lang
            self.app.save_config()
            messagebox.showinfo(
                _("dialog.restart_title"),
                _("dialog.restart_message"),
                parent=self.app.root
            )
            self.update_all_ui_text()

    def update_all_ui_text(self):
        _ = self.get
        app = self.app

        app.update_title()

        app.menubar.entryconfig(1, label=_("menu.file"))
        app.menubar.entryconfig(2, label=_("menu.edit"))
        app.menubar.entryconfig(3, label=_("menu.view"))
        app.menubar.entryconfig(4, label=_("menu.tools"))
        app.menubar.entryconfig(5, label=_("menu.settings"))
        app.menubar.entryconfig(6, label=_("menu.help"))

        app.file_menu.entryconfig(_("menu.file.open_code_file"), label=_("menu.file.open_code_file"))
        app.file_menu.entryconfig(_("menu.file.open_project"), label=_("menu.file.open_project"))
        app.file_menu.entryconfig(_("menu.file.compare_version"), label=_("menu.file.compare_version"))
        app.file_menu.entryconfig(_("menu.file.save_project"), label=_("menu.file.save_project"))
        app.file_menu.entryconfig(_("menu.file.save_project_as"), label=_("menu.file.save_project_as"))
        app.file_menu.entryconfig(_("menu.file.save_code_file"), label=_("menu.file.save_code_file"))
        app.file_menu.entryconfig(_("menu.file.import_excel"), label=_("menu.file.import_excel"))
        app.file_menu.entryconfig(_("menu.file.export_excel"), label=_("menu.file.export_excel"))
        app.file_menu.entryconfig(_("menu.file.export_json"), label=_("menu.file.export_json"))
        app.file_menu.entryconfig(_("menu.file.export_yaml"), label=_("menu.file.export_yaml"))
        app.file_menu.entryconfig(_("menu.file.extract_pot"), label=_("menu.file.extract_pot"))
        app.file_menu.entryconfig(_("menu.file.import_po"), label=_("menu.file.import_po"))
        app.file_menu.entryconfig(_("menu.file.export_po"), label=_("menu.file.export_po"))
        app.file_menu.entryconfig(_("menu.file.import_tm"), label=_("menu.file.import_tm"))
        app.file_menu.entryconfig(_("menu.file.export_tm"), label=_("menu.file.export_tm"))
        app.file_menu.entryconfig(_("menu.file.recent_files"), label=_("menu.file.recent_files"))
        app.file_menu.entryconfig(_("menu.file.exit"), label=_("menu.file.exit"))

        app.edit_menu.entryconfig(_("menu.edit.undo"), label=_("menu.edit.undo"))
        app.edit_menu.entryconfig(_("menu.edit.redo"), label=_("menu.edit.redo"))
        app.edit_menu.entryconfig(_("menu.edit.find_replace"), label=_("menu.edit.find_replace"))
        app.edit_menu.entryconfig(_("menu.edit.copy_original"), label=_("menu.edit.copy_original"))
        app.edit_menu.entryconfig(_("menu.edit.paste_translation"), label=_("menu.edit.paste_translation"))

        app.view_menu.entryconfig(_("menu.view.deduplicate"), label=_("menu.view.deduplicate"))
        app.view_menu.entryconfig(_("menu.view.show_ignored"), label=_("menu.view.show_ignored"))
        app.view_menu.entryconfig(_("menu.view.show_untranslated"), label=_("menu.view.show_untranslated"))
        app.view_menu.entryconfig(_("menu.view.show_translated"), label=_("menu.view.show_translated"))
        app.view_menu.entryconfig(_("menu.view.show_unreviewed"), label=_("menu.view.show_unreviewed"))

        app.tools_menu.entryconfig(_("menu.tools.apply_tm_all"), label=_("menu.tools.apply_tm_all"))
        app.tools_menu.entryconfig(_("menu.tools.clear_tm"), label=_("menu.tools.clear_tm"))
        app.tools_menu.entryconfig(_("menu.tools.ai_translate_selected"), label=_("menu.tools.ai_translate_selected"))
        app.tools_menu.entryconfig(_("menu.tools.ai_translate_all"), label=_("menu.tools.ai_translate_all"))
        app.tools_menu.entryconfig(_("menu.tools.stop_ai_batch"), label=_("menu.tools.stop_ai_batch"))
        app.tools_menu.entryconfig(_("menu.tools.project_instructions"), label=_("menu.tools.project_instructions"))
        app.tools_menu.entryconfig(_("menu.tools.ai_settings"), label=_("menu.tools.ai_settings"))
        app.tools_menu.entryconfig(_("menu.tools.extraction_rules"), label=_("menu.tools.extraction_rules"))
        app.tools_menu.entryconfig(_("menu.tools.reload_text"), label=_("menu.tools.reload_text"))

        app.settings_menu.entryconfig(_("menu.settings.auto_backup_tm"), label=_("menu.settings.auto_backup_tm"))
        app.settings_menu.entryconfig(_("menu.settings.keybindings"), label=_("menu.settings.keybindings"))
        app.settings_menu.entryconfig(_("menu.settings.language"), label=_("menu.settings.language"))

        app.help_menu.entryconfig(_("menu.help.about"), label=_("menu.help.about"))

        app.filter_label.config(text=_("toolbar.filter"))
        app.deduplicate_check.config(text=_("toolbar.deduplicate"))
        app.show_ignored_check.config(text=_("toolbar.ignored"))
        app.show_untranslated_check.config(text=_("toolbar.untranslated"))
        app.show_translated_check.config(text=_("toolbar.translated"))
        app.show_unreviewed_check.config(text=_("toolbar.unreviewed"))
        app.search_button.config(text=_("toolbar.search_button"))
        app.on_search_focus_out(None) # To reset placeholder text

        app.tree.heading("seq_id", text=_("treeview.col_seq"))
        app.tree.heading("status", text=_("treeview.col_status"))
        app.tree.heading("original", text=_("treeview.col_original"))
        app.tree.heading("translation", text=_("treeview.col_translation"))
        app.tree.heading("comment", text=_("treeview.col_comment"))
        app.tree.heading("reviewed", text=_("treeview.col_reviewed"))
        app.tree.heading("line", text=_("treeview.col_line"))

        app.details_outer_frame.config(text=_("details_pane.title"))
        app.original_text_label.config(text=_("details_pane.original_label"))
        app.translation_text_label.config(text=_("details_pane.translation_label"))
        app.apply_btn.config(text=_("details_pane.apply_button"))
        app.ai_translate_current_btn.config(text=_("details_pane.ai_button"))
        app.comment_label.config(text=_("details_pane.comment_label"))
        app.apply_comment_btn.config(text=_("details_pane.apply_comment_button"))
        app.toggle_ignore_btn.config(text=_("details_pane.ignore_checkbox")) # Note: this text is dynamic, might need special handling
        app.toggle_reviewed_btn.config(text=_("details_pane.reviewed_checkbox"))
        app.context_label.config(text=_("details_pane.context_label"))
        app.tm_label.config(text=_("details_pane.tm_label"))
        app.update_selected_tm_btn.config(text=_("details_pane.update_tm_button"))
        app.clear_selected_tm_btn.config(text=_("details_pane.clear_tm_button"))

        app.update_statusbar(_("statusbar.ready"))