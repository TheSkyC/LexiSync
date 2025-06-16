import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import shutil
import datetime
import time
import threading
from difflib import SequenceMatcher

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    TkinterDnD = None

from utils.config_manager import ConfigManager
from utils import constants
from services.localization_service import LocalizationService
from services.ai_translator import AITranslator
from services.termbase_service import TermbaseService
from services.project_service import ProjectService
from services.code_file_service import CodeFileService
from components.project_tab import ProjectTab
from dialogs.ai_settings_dialog import AISettingsDialog
from dialogs.hotkey_dialog import HotkeyDialog
from dialogs.search_dialog import AdvancedSearchDialog
from dialogs.statistics_dialog import StatisticsDialog


class OverwatchLocalizerApp:
    def __init__(self, root):
        self.root = root
        if TkinterDnD and not isinstance(root, TkinterDnD.Tk):
            self.root = TkinterDnD.DnDWrapper(self.root)

        self.config_manager = ConfigManager()
        self.loc = LocalizationService(self.config_manager.get('language', 'en_us'))

        self.root.title(f"{self.loc('app_title')} - v{constants.APP_VERSION}")
        self.root.geometry("1600x900")

        self.ai_translator = AITranslator(
            api_key=self.config_manager.get("ai_api_key"),
            model_name=self.config_manager.get("ai_model_name"),
            api_url=self.config_manager.get("ai_api_base_url")
        )
        self.termbase_service = TermbaseService()
        self.translation_memory = {}
        self.current_tm_file = None
        self._load_default_tm_excel()

        self.is_ai_translating_batch = False
        self.ai_batch_stop_flag = threading.Event()

        self._setup_main_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._setup_drag_drop()
        self.bind_hotkeys()

        self.update_ui_state()
        self.update_recent_files_menu()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_main_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=5, pady=5)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def _setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File Menu
        self.file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=self.loc('file_menu'), menu=self.file_menu)
        self.file_menu.add_command(label=self.loc('open_code_file'), command=self.open_code_file_dialog)
        self.file_menu.add_command(label=self.loc('open_project'), command=self.open_project_dialog)
        self.file_menu.add_command(label=self.loc('close_tab'), command=self.close_current_tab)
        self.file_menu.add_separator()
        self.file_menu.add_command(label=self.loc('save_project'), command=self.save_current_project)
        self.file_menu.add_command(label=self.loc('save_project_as'),
                                   command=lambda: self.save_current_project(ask_path=True))
        self.file_menu.add_command(label=self.loc('save_all_projects'), command=self.save_all_projects)
        self.file_menu.add_separator()
        self.file_menu.add_command(label=self.loc('save_translated_code'), command=self.save_code_file)
        self.file_menu.add_separator()
        self.file_menu.add_command(label=self.loc('import_tm'), command=self.import_tm_excel_dialog)
        self.file_menu.add_command(label=self.loc('export_tm'), command=self.export_tm_excel_dialog)
        self.file_menu.add_separator()
        self.recent_files_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label=self.loc('recent_files'), menu=self.recent_files_menu)
        self.file_menu.add_separator()
        self.file_menu.add_command(label=self.loc('exit'), command=self.on_closing)

        # Edit Menu
        self.edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=self.loc('edit_menu'), menu=self.edit_menu)
        self.edit_menu.add_command(label=self.loc('undo'), command=self.undo_action)
        self.edit_menu.add_command(label=self.loc('redo'), command=self.redo_action)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label=self.loc('find_replace'), command=self.show_advanced_search_dialog)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label=self.loc('copy_original'), command=self.copy_original_text)
        self.edit_menu.add_command(label=self.loc('paste_translation'), command=self.paste_to_translation)

        # Tools Menu
        self.tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=self.loc('tools_menu'), menu=self.tools_menu)
        self.tools_menu.add_command(label=self.loc('apply_tm_untranslated'),
                                    command=lambda: self.apply_tm_to_all_current_strings(self.get_current_tab(),
                                                                                         only_if_empty=True,
                                                                                         confirm=True))
        self.tools_menu.add_command(label=self.loc('clear_tm'), command=self.clear_entire_translation_memory)
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label=self.loc('ai_translate_selected'), command=self.ai_translate_selected)
        self.tools_menu.add_command(label=self.loc('ai_translate_all_untranslated'),
                                    command=self.ai_translate_all_untranslated)
        self.tools_menu.add_command(label=self.loc('stop_ai_batch'), command=self.stop_batch_ai_translation)
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label=self.loc('project_instructions'),
                                    command=self.show_project_custom_instructions_dialog)
        self.tools_menu.add_command(label=self.loc('ai_settings'), command=self.show_ai_settings_dialog)
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label=self.loc('compare_version'), command=self.compare_with_new_version)
        self.tools_menu.add_command(label=self.loc('project_statistics'), command=self.show_statistics_dialog)

        # Settings Menu
        self.settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=self.loc('settings_menu'), menu=self.settings_menu)
        self.auto_backup_tm_var = tk.BooleanVar(value=self.config_manager.get("auto_backup_tm_on_save", True))
        self.settings_menu.add_checkbutton(label=self.loc('auto_backup_tm'), variable=self.auto_backup_tm_var,
                                           command=lambda: self.config_manager.set('auto_backup_tm_on_save',
                                                                                   self.auto_backup_tm_var.get()))
        self.settings_menu.add_command(label=self.loc('hotkey_settings'), command=self.show_hotkey_dialog)

        lang_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label=self.loc('language'), menu=lang_menu)
        self.language_var = tk.StringVar(value=self.config_manager.get('language'))
        lang_menu.add_radiobutton(label="English", variable=self.language_var, value='en_us',
                                  command=self.change_language)
        lang_menu.add_radiobutton(label="简体中文", variable=self.language_var, value='zh_cn',
                                  command=self.change_language)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=self.loc('help_menu'), menu=help_menu)
        help_menu.add_command(label=self.loc('about'), command=self.about)

    def _setup_statusbar(self):
        self.statusbar_frame = ttk.Frame(self.root)
        self.statusbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.statusbar_text = tk.StringVar(value=self.loc('status_ready'))
        ttk.Label(self.statusbar_frame, textvariable=self.statusbar_text, anchor=tk.W, padding=(5, 2)).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        self.counts_text = tk.StringVar()
        ttk.Label(self.statusbar_frame, textvariable=self.counts_text, anchor=tk.E, padding=(5, 2)).pack(side=tk.RIGHT,
                                                                                                         padx=10)
        self.progress_bar = ttk.Progressbar(self.statusbar_frame, orient=tk.HORIZONTAL, length=150, mode='determinate')

    def _setup_drag_drop(self):
        if TkinterDnD:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.handle_drop)

    def bind_hotkeys(self):
        hotkeys = self.config_manager.get('hotkeys', constants.DEFAULT_HOTKEYS)
        self.root.bind_all(hotkeys.get('save_project', '<Control-s>'), lambda e: self.save_current_project())
        self.root.bind_all(hotkeys.get('open_project', '<Control-o>'), lambda e: self.open_project_dialog())
        self.root.bind_all(hotkeys.get('find_replace', '<Control-f>'), lambda e: self.show_advanced_search_dialog())
        # Other hotkeys are bound within the ProjectTab class itself

    def get_current_tab(self):
        try:
            selected_tab_id = self.notebook.select()
            return self.notebook.nametowidget(selected_tab_id)
        except (tk.TclError, KeyError):
            return None

    def on_tab_changed(self, event):
        self.update_ui_state()
        self.update_counts_display()

    def update_tab_title(self, tab):
        try:
            self.notebook.tab(tab, text=tab.get_tab_text())
        except tk.TclError:
            pass

    def open_code_file_dialog(self):
        filepath = filedialog.askopenfilename(
            title=self.loc('open_code_file'),
            filetypes=[("Overwatch Workshop Files", "*.ow;*.txt"), ("All Files", "*.*")],
            initialdir=self.config_manager.get("last_dir", os.getcwd())
        )
        if filepath:
            self.create_new_tab(filepath, is_project_file=False)

    def open_project_dialog(self):
        filepath = filedialog.askopenfilename(
            title=self.loc('open_project'),
            filetypes=[("Overwatch Project Files", f"*{constants.PROJECT_FILE_EXTENSION}"), ("All Files", "*.*")],
            initialdir=self.config_manager.get("last_dir", os.getcwd())
        )
        if filepath:
            self.create_new_tab(filepath, is_project_file=True)

    def create_new_tab(self, file_path, is_project_file):
        tab = ProjectTab(self.notebook, self, file_path, is_project_file)
        self.notebook.add(tab, text=tab.get_tab_text())
        self.notebook.select(tab)
        self.config_manager.add_to_recent_files(file_path)
        self.update_recent_files_menu()
        self.update_ui_state()

    def close_current_tab(self):
        tab = self.get_current_tab()
        if not tab: return
        if tab.is_modified:
            response = messagebox.askyesnocancel("Save Changes?",
                                                 f"Project '{tab.get_tab_text()}' has unsaved changes. Save before closing?",
                                                 parent=self.root)
            if response is True:
                if not tab.save_project():
                    return
            elif response is None:
                return

        if tab.docked_window:
            tab.docked_window.destroy()

        self.notebook.forget(tab)
        self.update_ui_state()

    def save_current_project(self, ask_path=False):
        tab = self.get_current_tab()
        if tab:
            tab.save_project(ask_path)

    def save_all_projects(self):
        for tab in self.notebook.tabs():
            widget = self.notebook.nametowidget(tab)
            if widget.is_modified:
                self.notebook.select(widget)
                widget.save_project()

    def on_closing(self):
        unsaved_tabs = [tab for tab in self.notebook.tabs() if self.notebook.nametowidget(tab).is_modified]
        if unsaved_tabs:
            if not messagebox.askyesno(self.loc('confirm_exit_title'), self.loc('confirm_exit_msg')):
                return

        if self.is_ai_translating_batch:
            self.stop_batch_ai_translation(silent=True)

        if self.current_tm_file and self.translation_memory:
            self.save_tm_to_excel(self.current_tm_file, silent=True, backup=self.auto_backup_tm_var.get())

        self.config_manager.save_config()
        self.root.destroy()

    def update_ui_state(self):
        tab = self.get_current_tab()
        has_tab = tab is not None
        has_content = has_tab and bool(tab.translatable_objects)
        has_selection = has_tab and tab.current_selected_ts_id is not None

        # File menu
        self.file_menu.entryconfig(self.loc('close_tab'), state=tk.NORMAL if has_tab else tk.DISABLED)
        self.file_menu.entryconfig(self.loc('save_project'), state=tk.NORMAL if has_content else tk.DISABLED)
        self.file_menu.entryconfig(self.loc('save_project_as'), state=tk.NORMAL if has_content else tk.DISABLED)
        self.file_menu.entryconfig(self.loc('save_all_projects'), state=tk.NORMAL if any(
            self.notebook.nametowidget(t).is_modified for t in self.notebook.tabs()) else tk.DISABLED)
        self.file_menu.entryconfig(self.loc('save_translated_code'),
                                   state=tk.NORMAL if has_content and tab.current_code_file_path else tk.DISABLED)

        # Edit menu
        self.edit_menu.entryconfig(self.loc('undo'), state=tk.NORMAL if has_tab and tab.undo_history else tk.DISABLED)
        self.edit_menu.entryconfig(self.loc('redo'), state=tk.NORMAL if has_tab and tab.redo_history else tk.DISABLED)
        self.edit_menu.entryconfig(self.loc('find_replace'), state=tk.NORMAL if has_content else tk.DISABLED)
        self.edit_menu.entryconfig(self.loc('copy_original'), state=tk.NORMAL if has_selection else tk.DISABLED)
        self.edit_menu.entryconfig(self.loc('paste_translation'), state=tk.NORMAL if has_selection else tk.DISABLED)

        # Tools menu
        self.tools_menu.entryconfig(self.loc('apply_tm_untranslated'), state=tk.NORMAL if has_content else tk.DISABLED)
        self.tools_menu.entryconfig(self.loc('ai_translate_selected'),
                                    state=tk.NORMAL if has_selection and not self.is_ai_translating_batch else tk.DISABLED)
        self.tools_menu.entryconfig(self.loc('ai_translate_all_untranslated'),
                                    state=tk.NORMAL if has_content and not self.is_ai_translating_batch else tk.DISABLED)
        self.tools_menu.entryconfig(self.loc('stop_ai_batch'),
                                    state=tk.NORMAL if self.is_ai_translating_batch else tk.DISABLED)
        self.tools_menu.entryconfig(self.loc('project_instructions'),
                                    state=tk.NORMAL if has_tab and tab.current_project_file_path else tk.DISABLED)
        self.tools_menu.entryconfig(self.loc('compare_version'), state=tk.NORMAL if has_content else tk.DISABLED)
        self.tools_menu.entryconfig(self.loc('project_statistics'), state=tk.NORMAL if has_content else tk.DISABLED)

        if has_tab:
            tab.ai_translate_current_btn.config(
                state=tk.NORMAL if has_selection and not self.is_ai_translating_batch else tk.DISABLED)
            tab.apply_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)
            tab.apply_comment_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)
            tab.toggle_ignore_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)
            tab.toggle_reviewed_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)

    def update_statusbar(self, text, persistent=False):
        self.statusbar_text.set(text)
        if not persistent:
            self.root.after(5000, lambda: self.clear_statusbar_if_unchanged(text))

    def clear_statusbar_if_unchanged(self, original_text):
        if self.statusbar_text.get() == original_text:
            self.statusbar_text.set(self.loc('status_ready'))

    def update_counts_display(self):
        tab = self.get_current_tab()
        if not tab or not hasattr(tab, 'translatable_objects'):
            self.counts_text.set("")
            return

        displayed = len(tab.displayed_string_ids)
        translated = sum(1 for iid in tab.displayed_string_ids if
                         (ts := tab._find_ts_obj_by_id(iid)) and ts.translation.strip() and not ts.is_ignored)
        untranslated = sum(1 for iid in tab.displayed_string_ids if
                           (ts := tab._find_ts_obj_by_id(iid)) and not ts.translation.strip() and not ts.is_ignored)
        ignored = sum(1 for iid in tab.displayed_string_ids if (ts := tab._find_ts_obj_by_id(iid)) and ts.is_ignored)

        self.counts_text.set(
            f"Displayed: {displayed} | Translated: {translated} | Untranslated: {untranslated} | Ignored: {ignored}")

    def undo_action(self):
        tab = self.get_current_tab()
        if tab: tab.undo_action()

    def redo_action(self):
        tab = self.get_current_tab()
        if tab: tab.redo_action()

    def copy_original_text(self):
        tab = self.get_current_tab()
        if tab: tab.cm_copy_original()

    def paste_to_translation(self):
        tab = self.get_current_tab()
        if tab:
            try:
                content = self.root.clipboard_get()
                if tab.current_selected_ts_id and isinstance(content, str):
                    tab.translation_edit_text.delete('1.0', tk.END)
                    tab.translation_edit_text.insert('1.0', content)
                    tab.apply_translation_from_button()
            except tk.TclError:
                pass

    def change_language(self):
        lang = self.language_var.get()
        self.config_manager.set('language', lang)
        messagebox.showinfo(self.loc('restart_required_title'), self.loc('restart_required_msg'))

    def show_hotkey_dialog(self):
        actions = {
            "apply_and_next": "Apply and Go to Next Untranslated",
            "ai_translate_selected": "AI Translate Selected",
            "toggle_reviewed": "Toggle Reviewed Status",
            "toggle_ignored": "Toggle Ignored Status",
            "copy_original": "Copy Original Text",
            "paste_translation": "Paste to Translation",
            "save_project": "Save Project",
            "open_project": "Open Project",
            "find_replace": "Find/Replace"
        }
        HotkeyDialog(self.root, "Hotkey Settings", self.config_manager, actions, self.bind_hotkeys)

    def show_advanced_search_dialog(self):
        tab = self.get_current_tab()
        if tab: AdvancedSearchDialog(self.root, self.loc('find_replace'), tab)

    def show_statistics_dialog(self):
        tab = self.get_current_tab()
        if tab: StatisticsDialog(self.root, self.loc('project_statistics'), tab.translatable_objects)

    def compare_with_new_version(self):
        tab = self.get_current_tab()
        if not tab: return

        filepath = filedialog.askopenfilename(
            title="Select New Version of Code File",
            filetypes=[("Overwatch Workshop Files", "*.ow;*.txt"), ("All Files", "*.*")],
            initialdir=self.config_manager.get("last_dir", os.getcwd())
        )
        if not filepath: return

        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                new_code = f.read()

            new_strings = CodeFileService.extract_translatable_strings(new_code)
            old_strings_map = {s.original_semantic: s for s in tab.translatable_objects}

            matched_count = 0
            inherited_count = 0
            new_count = 0

            for new_str in new_strings:
                if new_str.original_semantic in old_strings_map:
                    old_str = old_strings_map[new_str.original_semantic]
                    new_str.translation = old_str.translation
                    new_str.comment = old_str.comment
                    new_str.is_reviewed = old_str.is_reviewed
                    new_str.is_ignored = old_str.is_ignored
                    matched_count += 1
                else:
                    # Fuzzy match
                    best_match = None
                    highest_ratio = 0.95
                    for old_semantic, old_str_obj in old_strings_map.items():
                        ratio = SequenceMatcher(None, new_str.original_semantic, old_semantic).ratio()
                        if ratio > highest_ratio:
                            highest_ratio = ratio
                            best_match = old_str_obj

                    if best_match:
                        new_str.translation = best_match.translation
                        new_str.comment = f"Inherited from (Similarity: {highest_ratio:.0%}): {best_match.original_semantic[:50]}..."
                        new_str.is_reviewed = False
                        new_str.is_inherited = True
                        inherited_count += 1
                    else:
                        new_count += 1

            tab.translatable_objects = new_strings
            tab.original_raw_code_content = new_code
            tab.current_code_file_path = filepath
            tab.mark_modified()
            tab.refresh_treeview()

            messagebox.showinfo("Comparison Complete",
                                f"Comparison finished.\n\n"
                                f"Exact Matches: {matched_count}\n"
                                f"Inherited (Fuzzy): {inherited_count}\n"
                                f"New Strings: {new_count}\n\n"
                                f"Inherited items are marked as 'unreviewed'.")

        except Exception as e:
            messagebox.showerror(self.loc('error'), f"Failed to compare versions: {e}")

    def about(self):
        messagebox.showinfo(self.loc('about'),
                            f"{self.loc('app_title')} v{constants.APP_VERSION}\n"
                            "Author: 骰子掷上帝\n"
                            "This is a refactored and enhanced version.")

    # AI Translation methods
    def ai_translate_selected(self):
        tab = self.get_current_tab()
        if not tab or not tab.current_selected_ts_id: return
        self._initiate_ai_translation([tab._find_ts_obj_by_id(tab.current_selected_ts_id)])

    def ai_translate_all_untranslated(self):
        tab = self.get_current_tab()
        if not tab: return
        items_to_translate = [ts for ts in tab.translatable_objects if not ts.translation.strip() and not ts.is_ignored]
        if not items_to_translate:
            messagebox.showinfo("AI Translate", "No untranslated items to process.", parent=self.root)
            return
        self._initiate_ai_translation(items_to_translate)

    def _initiate_ai_translation(self, items):
        if not items: return
        if self.is_ai_translating_batch:
            messagebox.showwarning("AI Busy", "An AI batch translation is already in progress.", parent=self.root)
            return
        if not self.ai_translator.api_key:
            messagebox.showerror("API Key Missing", "Please set your AI API key in Tools > AI Settings.",
                                 parent=self.root)
            return

        if len(items) > 1:
            if not messagebox.askyesno("Confirm Batch AI",
                                       f"This will start an AI translation job for {len(items)} items. Continue?",
                                       parent=self.root):
                return

        self.is_ai_translating_batch = True
        self.ai_batch_stop_flag.clear()
        self.update_ui_state()
        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)
        self.progress_bar['maximum'] = len(items)
        self.progress_bar['value'] = 0

        thread = threading.Thread(target=self._run_ai_batch, args=(items,), daemon=True)
        thread.start()

    def _run_ai_batch(self, items):
        tab = self.get_current_tab()
        if not tab: return

        config = self.config_manager.config
        target_language = config.get("ai_target_language", "中文")
        prompt_template = config.get("ai_prompt_template", constants.DEFAULT_AI_PROMPT_TEMPLATE)
        interval_ms = config.get("ai_api_interval", 200)

        successful_translations = []

        for i, ts_obj in enumerate(items):
            if self.ai_batch_stop_flag.is_set():
                break

            self.update_statusbar(f"AI Translating {i + 1}/{len(items)}...", persistent=True)
            self.root.after(0, self.progress_bar.config, {'value': i + 1})

            context_str = self._generate_ai_context_string(tab, ts_obj.id, 'translation')
            orig_context_str = self._generate_ai_context_string(tab, ts_obj.id, 'original')
            termbase_mappings = self.termbase_service.get_mappings_for_text(ts_obj.original_semantic)

            try:
                translated_text = self.ai_translator.translate(
                    ts_obj.original_semantic, target_language, prompt_template,
                    context_str, orig_context_str, tab.project_custom_instructions, termbase_mappings
                )
                if translated_text:
                    successful_translations.append((ts_obj, translated_text))
            except Exception as e:
                print(f"AI translation failed for '{ts_obj.original_semantic[:20]}...': {e}")

            time.sleep(interval_ms / 1000)

        self.root.after(0, self._finalize_ai_batch, successful_translations)

    def _finalize_ai_batch(self, successful_translations):
        tab = self.get_current_tab()
        if not tab: return

        if successful_translations:
            changes = []
            for ts_obj, new_text in successful_translations:
                old_text = ts_obj.get_translation_for_storage_and_tm()
                ts_obj.set_translation_internal(new_text)
                changes.append({'string_id': ts_obj.id, 'field': 'translation', 'old_value': old_text,
                                'new_value': ts_obj.get_translation_for_storage_and_tm()})

            if changes:
                tab.add_to_undo_history('bulk_ai_translate', {'changes': changes})
                tab.refresh_treeview(preserve_selection=True)

        self.is_ai_translating_batch = False
        self.update_ui_state()
        self.progress_bar.pack_forget()
        self.update_statusbar(f"AI batch finished. Translated {len(successful_translations)} items.", persistent=True)

    def stop_batch_ai_translation(self, silent=False):
        if self.is_ai_translating_batch:
            self.ai_batch_stop_flag.set()
            if not silent:
                messagebox.showinfo("AI Translation", "AI batch translation will stop after the current item.",
                                    parent=self.root)

    def _generate_ai_context_string(self, tab, current_ts_id, context_type):
        use_key = "ai_use_translation_context" if context_type == 'translation' else "ai_use_original_context"
        neighbors_key = "ai_context_neighbors" if context_type == 'translation' else "ai_original_context_neighbors"

        if not self.config_manager.get(use_key, False):
            return ""

        max_neighbors = self.config_manager.get(neighbors_key, 0)
        try:
            current_index = [i for i, ts in enumerate(tab.translatable_objects) if ts.id == current_ts_id][0]
        except IndexError:
            return ""

        context_items = []
        # Preceding
        count = 0
        for i in range(current_index - 1, -1, -1):
            if max_neighbors > 0 and count >= max_neighbors: break
            ts = tab.translatable_objects[i]
            if context_type == 'translation' and ts.translation.strip() and not ts.is_ignored:
                context_items.insert(0, f"{ts.original_semantic} -> {ts.get_translation_for_storage_and_tm()}")
                count += 1
            elif context_type == 'original':
                context_items.insert(0, ts.original_semantic)
                count += 1

        # Succeeding
        count = 0
        for i in range(current_index + 1, len(tab.translatable_objects)):
            if max_neighbors > 0 and count >= max_neighbors: break
            ts = tab.translatable_objects[i]
            if context_type == 'translation' and ts.translation.strip() and not ts.is_ignored:
                context_items.append(f"{ts.original_semantic} -> {ts.get_translation_for_storage_and_tm()}")
                count += 1
            elif context_type == 'original':
                context_items.append(ts.original_semantic)
                count += 1

        return " ||| ".join(item.replace("\n", " ").replace("\\n", " ") for item in context_items)

    # Other methods... (TM, recent files, etc.)
    def _load_default_tm_excel(self):
        default_path = os.path.join(os.getcwd(), constants.TM_FILE_EXCEL)
        if os.path.exists(default_path):
            self.load_tm_from_excel(default_path, silent=True)

    def load_tm_from_excel(self, filepath, silent=False):
        try:
            wb = load_workbook(filepath, read_only=True)
            ws = wb.active
            loaded_count = 0
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and len(row) >= 2 and row[0] and row[1]:
                    self.translation_memory[str(row[0])] = str(row[1])
                    loaded_count += 1
            self.current_tm_file = filepath
            if not silent:
                messagebox.showinfo("TM Loaded", f"Loaded {loaded_count} entries from {os.path.basename(filepath)}.")
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load TM from Excel: {e}")

    def save_tm_to_excel(self, filepath, silent=False, backup=True):
        if not self.translation_memory:
            if not silent: messagebox.showinfo("TM", "Translation memory is empty. Nothing to save.")
            return

        if backup and self.auto_backup_tm_var.get() and os.path.exists(filepath):
            backup_dir = os.path.join(os.path.dirname(filepath), "tm_backups")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base, ext = os.path.splitext(os.path.basename(filepath))
            backup_path = os.path.join(backup_dir, f"{base}_{timestamp}{ext}")
            try:
                shutil.copy2(filepath, backup_path)
            except Exception as e:
                print(f"TM backup failed: {e}")

        wb = Workbook()
        ws = wb.active
        ws.title = "TranslationMemory"
        ws.append(["Original", "Translation"])
        for orig, trans in self.translation_memory.items():
            ws.append([orig, trans])

        try:
            wb.save(filepath)
            self.current_tm_file = filepath
            if not silent:
                messagebox.showinfo("TM Saved", f"Translation memory saved to {os.path.basename(filepath)}.")
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to save TM: {e}")

    def apply_tm_to_all_current_strings(self, tab, silent=False, only_if_empty=False, confirm=False,
                                        selected_only=False):
        if not tab or not tab.translatable_objects or not self.translation_memory:
            return 0

        if confirm and not messagebox.askyesno("Confirm", "This will apply TM to all untranslated strings. Continue?"):
            return 0

        items_to_process = tab._get_selected_ts_objects() if selected_only else tab.translatable_objects
        applied_count = 0
        changes = []
        for ts_obj in items_to_process:
            if ts_obj.is_ignored: continue
            if only_if_empty and ts_obj.translation.strip(): continue

            if ts_obj.original_semantic in self.translation_memory:
                tm_trans = self.translation_memory[ts_obj.original_semantic]
                if ts_obj.get_translation_for_storage_and_tm() != tm_trans:
                    old_trans = ts_obj.get_translation_for_storage_and_tm()
                    ts_obj.set_translation_internal(tm_trans.replace("\\n", "\n"))
                    changes.append(
                        {'string_id': ts_obj.id, 'field': 'translation', 'old_value': old_trans, 'new_value': tm_trans})
                    applied_count += 1

        if changes:
            tab.add_to_undo_history('bulk_tm_apply', {'changes': changes})
            tab.refresh_treeview(preserve_selection=True)

        if not silent:
            messagebox.showinfo("TM Apply", f"Applied TM to {applied_count} strings.")
        return applied_count

    def update_recent_files_menu(self):
        self.recent_files_menu.delete(0, tk.END)
        recent_files = self.config_manager.get("recent_files", [])
        if not recent_files:
            self.recent_files_menu.add_command(label=self.loc('no_recent_files'), state=tk.DISABLED)
            return
        for i, filepath in enumerate(recent_files):
            self.recent_files_menu.add_command(label=f"{i + 1}: {filepath}",
                                               command=lambda p=filepath: self.open_recent_file(p))
        self.recent_files_menu.add_separator()
        self.recent_files_menu.add_command(label=self.loc('clear_recent_files'), command=self.clear_recent_files)

    def open_recent_file(self, filepath):
        if not os.path.exists(filepath):
            messagebox.showerror("File Not Found", f"File '{filepath}' does not exist.")
            recent = self.config_manager.get("recent_files", [])
            if filepath in recent:
                recent.remove(filepath)
                self.config_manager.set("recent_files", recent)
                self.update_recent_files_menu()
            return

        is_project = filepath.lower().endswith(constants.PROJECT_FILE_EXTENSION)
        self.create_new_tab(filepath, is_project_file=is_project)

    def clear_recent_files(self):
        if messagebox.askyesno("Confirm", "Clear all recent file history?"):
            self.config_manager.set("recent_files", [])
            self.update_recent_files_menu()

    def handle_drop(self, event):
        try:
            filepath = self.root.tk.splitlist(event.data)[0]
            if os.path.isfile(filepath):
                is_proj = filepath.lower().endswith(constants.PROJECT_FILE_EXTENSION)
                is_code = filepath.lower().endswith((".ow", ".txt"))
                if is_proj or is_code:
                    self.create_new_tab(filepath, is_project_file=is_proj)
                else:
                    self.update_statusbar(f"Drop failed: Invalid file type '{os.path.basename(filepath)}'")
        except Exception as e:
            messagebox.showerror("Drop Error", f"Error processing dropped file: {e}")

    def show_ai_settings_dialog(self):
        AISettingsDialog(self.root, self.loc('ai_settings'), self.config_manager, self.ai_translator)

    def show_project_custom_instructions_dialog(self):
        tab = self.get_current_tab()
        if not tab: return
        new_instructions = simpledialog.askstring("Project Instructions", "Enter project-specific instructions for AI:",
                                                  initialvalue=tab.project_custom_instructions)
        if new_instructions is not None:
            tab.project_custom_instructions = new_instructions
            tab.mark_modified()

    def save_code_file(self):
        tab = self.get_current_tab()
        if not tab or not tab.current_code_file_path: return

        base, ext = os.path.splitext(tab.current_code_file_path)
        new_filepath = filedialog.asksaveasfilename(
            initialfile=f"{base}_translated{ext}",
            defaultextension=ext,
            filetypes=[("Overwatch Workshop Files", "*.ow;*.txt"), ("All Files", "*.*")]
        )
        if not new_filepath: return

        try:
            ProjectService.save_code_file(new_filepath, tab.original_raw_code_content, tab.translatable_objects)
            self.update_statusbar(self.loc('status_code_saved', os.path.basename(new_filepath)), persistent=True)
        except Exception as e:
            messagebox.showerror(self.loc('error'), f"Failed to save code file: {e}")

    def import_tm_excel_dialog(self):
        filepath = filedialog.askopenfilename(title="Import Translation Memory", filetypes=[("Excel Files", "*.xlsx")])
        if filepath:
            self.load_tm_from_excel(filepath)

    def export_tm_excel_dialog(self):
        filepath = filedialog.asksaveasfilename(title="Export Translation Memory",
                                                filetypes=[("Excel Files", "*.xlsx")], defaultextension=".xlsx",
                                                initialfile=constants.TM_FILE_EXCEL)
        if filepath:
            self.save_tm_to_excel(filepath, backup=False)

    def clear_entire_translation_memory(self):
        if messagebox.askyesno("Confirm", "Clear all in-memory TM entries? This cannot be undone."):
            self.translation_memory.clear()
            self.update_statusbar("In-memory TM cleared.")