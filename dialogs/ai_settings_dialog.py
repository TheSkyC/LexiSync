# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import threading
from services.ai_translator import AITranslator
from utils.constants import DEFAULT_API_URL, DEFAULT_PROMPT_STRUCTURE
from utils.localization import setup_translation, get_available_languages, _
from services.prompt_service import generate_prompt_from_structure
from dialogs.prompt_manager_dialog import PromptManagerDialog

class AISettingsDialog(tk.Toplevel):
    def __init__(self, parent, title, app_config_ref, save_config_callback, ai_translator_ref, app_instance):
        super().__init__(parent)
        self.app_config = app_config_ref
        self.save_config_callback = save_config_callback
        self.ai_translator_instance = ai_translator_ref
        self.result = None
        self.app = app_instance

        self.initial_api_key = self.app_config.get("ai_api_key", "")
        self.initial_api_base_url = self.app_config.get("ai_api_base_url", DEFAULT_API_URL)
        self.initial_target_language = self.app_config.get("ai_target_language", _("Target_Languege"))
        self.initial_api_interval = self.app_config.get("ai_api_interval", 200)
        self.initial_model_name = self.app_config.get("ai_model_name", "deepseek-chat")
        self.initial_max_concurrent_requests = self.app_config.get("ai_max_concurrent_requests", 1)
        self.initial_use_context = self.app_config.get("ai_use_translation_context", False)
        self.initial_context_neighbors = self.app_config.get("ai_context_neighbors", 0)
        self.initial_use_original_context = self.app_config.get("ai_use_original_context", True)
        self.initial_original_context_neighbors = self.app_config.get("ai_original_context_neighbors", 3)

        self.withdraw()
        if parent.winfo_viewable():
            self.transient(parent)
        if title:
            self.title(title)

        self.parent = parent

        main_container = ttk.Frame(self)
        main_container.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        main_container.grid_columnconfigure(0, weight=1)

        self.initial_focus = self.body(main_container)
        self.buttonbox(main_container)

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        if self.parent is not None:
            self.geometry(f"+{parent.winfo_rootx() + 50}+{parent.winfo_rooty() + 50}")

        self.deiconify()
        if self.initial_focus:
            self.initial_focus.focus_set()

        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def body(self, master):
        master.columnconfigure(1, weight=1)

        api_frame = ttk.LabelFrame(master, text=_("API Connection & Model Settings"), padding=(10, 5))
        api_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        api_frame.columnconfigure(1, weight=1)

        api_row_idx = 0
        ttk.Label(api_frame, text=_("API Key:")).grid(row=api_row_idx, column=0, sticky=tk.W, padx=5, pady=3)
        self.api_key_var = tk.StringVar(value=self.initial_api_key)
        self.api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, show="*", width=60)
        self.api_key_entry.grid(row=api_row_idx, column=1, sticky=tk.EW, padx=5, pady=3)
        api_row_idx += 1

        ttk.Label(api_frame, text=_("API Base URL:")).grid(row=api_row_idx, column=0, sticky=tk.W, padx=5, pady=3)
        self.api_base_url_var = tk.StringVar(value=self.initial_api_base_url)
        self.api_base_url_entry = ttk.Entry(api_frame, textvariable=self.api_base_url_var, width=60)
        self.api_base_url_entry.grid(row=api_row_idx, column=1, sticky=tk.EW, padx=5, pady=3)
        api_row_idx += 1

        ttk.Label(api_frame, text=_("Model Name:")).grid(row=api_row_idx, column=0, sticky=tk.W, padx=5, pady=3)
        self.model_name_var = tk.StringVar(value=self.initial_model_name)
        self.model_name_entry = ttk.Entry(api_frame, textvariable=self.model_name_var, width=60)
        self.model_name_entry.grid(row=api_row_idx, column=1, sticky=tk.EW, padx=5, pady=3)

        trans_frame = ttk.LabelFrame(master, text=_("Translation & Context Settings"), padding=(10, 5))
        trans_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        trans_frame.columnconfigure(1, weight=1)

        trans_row_idx = 0
        ttk.Label(trans_frame, text=_("Target Language:")).grid(row=trans_row_idx, column=0, sticky=tk.W, padx=5, pady=3)
        self.target_language_var = tk.StringVar(value=self.initial_target_language)
        self.target_language_entry = ttk.Entry(trans_frame, textvariable=self.target_language_var, width=60)
        self.target_language_entry.grid(row=trans_row_idx, column=1, sticky=tk.EW, padx=5, pady=3)
        trans_row_idx += 1

        ttk.Label(trans_frame, text=_("API Call Interval (ms):")).grid(row=trans_row_idx, column=0, sticky=tk.W, padx=5, pady=3)
        self.api_interval_var = tk.IntVar(value=self.initial_api_interval)
        self.api_interval_spinbox = tk.Spinbox(trans_frame, from_=0, to=10000, increment=50,
                                               textvariable=self.api_interval_var, width=10)
        self.api_interval_spinbox.grid(row=trans_row_idx, column=1, sticky=tk.W, padx=5, pady=3)
        trans_row_idx += 1

        ttk.Label(trans_frame, text=_("Max Concurrent Requests:")).grid(row=trans_row_idx, column=0, sticky=tk.W, padx=5, pady=3)
        self.max_concurrent_requests_var = tk.IntVar(value=self.initial_max_concurrent_requests)
        self.max_concurrent_requests_spinbox = tk.Spinbox(trans_frame, from_=1, to=10, increment=1,
                                                          textvariable=self.max_concurrent_requests_var, width=10)
        self.max_concurrent_requests_spinbox.grid(row=trans_row_idx, column=1, sticky=tk.W, padx=5, pady=3)
        trans_row_idx += 1

        self.use_original_context_var = tk.BooleanVar(value=self.initial_use_original_context)
        self.use_original_context_check = ttk.Checkbutton(trans_frame, text=_("Use nearby original text as context"),
                                                          variable=self.use_original_context_var,
                                                          command=self.toggle_context_neighbors_state)
        self.use_original_context_check.grid(row=trans_row_idx, column=0, columnspan=2, sticky=tk.W, padx=5,
                                             pady=(5, 0))
        trans_row_idx += 1

        original_context_neighbor_frame = ttk.Frame(trans_frame)
        original_context_neighbor_frame.grid(row=trans_row_idx, column=0, columnspan=2, sticky=tk.W, padx=25)
        ttk.Label(original_context_neighbor_frame, text=_("Use nearby")).pack(side=tk.LEFT)
        self.original_context_neighbors_var = tk.IntVar(value=self.initial_original_context_neighbors)
        self.original_context_neighbors_spinbox = tk.Spinbox(original_context_neighbor_frame, from_=0, to=10,
                                                             increment=1,
                                                             textvariable=self.original_context_neighbors_var, width=5)
        self.original_context_neighbors_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(original_context_neighbor_frame, text=_("original strings (0 for all)")).pack(side=tk.LEFT)
        trans_row_idx += 1

        self.use_context_var = tk.BooleanVar(value=self.initial_use_context)
        self.use_context_check = ttk.Checkbutton(trans_frame, text=_("Use nearby translated text as context"),
                                                 variable=self.use_context_var,
                                                 command=self.toggle_context_neighbors_state)
        self.use_context_check.grid(row=trans_row_idx, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5, 0))
        trans_row_idx += 1

        context_neighbor_frame = ttk.Frame(trans_frame)
        context_neighbor_frame.grid(row=trans_row_idx, column=0, columnspan=2, sticky=tk.W, padx=25)
        ttk.Label(context_neighbor_frame, text=_("Use nearby")).pack(side=tk.LEFT)
        self.context_neighbors_var = tk.IntVar(value=self.initial_context_neighbors)
        self.context_neighbors_spinbox = tk.Spinbox(context_neighbor_frame, from_=0, to=10, increment=1,
                                                    textvariable=self.context_neighbors_var, width=5)
        self.context_neighbors_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(context_neighbor_frame, text=_("translations (0 for all)")).pack(side=tk.LEFT)

        self.test_status_label = ttk.Label(master, text="", wraplength=550)
        self.test_status_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(10, 5))

        self.toggle_context_neighbors_state()
        return self.api_key_entry

    def toggle_context_neighbors_state(self):
        trans_state = tk.NORMAL if self.use_context_var.get() else tk.DISABLED
        self.context_neighbors_spinbox.config(state=trans_state)

        orig_state = tk.NORMAL if self.use_original_context_var.get() else tk.DISABLED
        self.original_context_neighbors_spinbox.config(state=orig_state)

    def buttonbox(self, master):
        main_frame = ttk.Frame(master)
        main_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT)

        prompt_btn = ttk.Button(left_frame, text=_("Prompt Manager..."), command=self.show_prompt_manager)
        prompt_btn.pack(side=tk.LEFT, padx=(0, 10))

        test_btn = ttk.Button(right_frame, text=_("Test Connection"), width=10, command=self.test_api_connection_dialog)
        test_btn.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        ok_btn = ttk.Button(right_frame, text=_("OK"), width=10, command=self.ok, default=tk.ACTIVE)
        ok_btn.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        cancel_btn = ttk.Button(right_frame, text=_("Cancel"), width=10, command=self.cancel)
        cancel_btn.pack(side=tk.LEFT, pady=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

    def show_prompt_manager(self):
        PromptManagerDialog(self, _("AI Prompt Manager"), self.app)

    def test_api_connection_dialog(self):
        self.test_status_label.config(text=_("Testing..."))
        self.update_idletasks()

        api_key = self.api_key_var.get()
        api_url = self.api_base_url_var.get().strip() or DEFAULT_API_URL
        model_name = self.model_name_var.get().strip()

        if not api_key:
            messagebox.showerror(_("Test Failed"), _("API Key is not filled."), parent=self)
            self.test_status_label.config(text=_("Test failed: API Key is not filled."))
            return

        temp_translator = AITranslator(api_key, model_name, api_url)

        def _test_in_thread():
            placeholders = {'[Target Language]': _('中文'), '[Custom Translate]': '', '[Untranslated Context]': '',
                            '[Translated Context]': ''}
            test_prompt = generate_prompt_from_structure(
                self.app_config.get("ai_prompt_structure", DEFAULT_PROMPT_STRUCTURE), placeholders)

            success, message = temp_translator.test_connection(system_prompt=test_prompt)
            self.after(0, self._show_test_result, success, message)

        threading.Thread(target=_test_in_thread, daemon=True).start()

    def _show_test_result(self, success, message):
        if self.winfo_exists():
            self.test_status_label.config(text=message)
            if success:
                messagebox.showinfo(_("Test Connection"), message, parent=self)
            else:
                messagebox.showerror(_("Test Connection"), message, parent=self)

    def ok(self, event=None):
        if self.apply():
            self.destroy()

    def cancel(self, event=None):
        self.destroy()

    def apply(self):
        api_key = self.api_key_var.get()
        api_base_url = self.api_base_url_var.get().strip()
        target_language = self.target_language_var.get().strip()
        model_name = self.model_name_var.get().strip()
        api_interval = self.api_interval_var.get()
        use_context = self.use_context_var.get()
        context_neighbors = self.context_neighbors_var.get()
        use_original_context = self.use_original_context_var.get()
        original_context_neighbors = self.original_context_neighbors_var.get()
        max_concurrent_requests = self.max_concurrent_requests_var.get()

        if not target_language:
            messagebox.showerror(_("Error"), _("Target language cannot be empty."), parent=self)
            self.target_language_entry.focus_set()
            return False
        if not model_name:
            messagebox.showerror(_("Error"), _("Model name cannot be empty."), parent=self)
            self.model_name_entry.focus_set()
            return False
        if api_interval < 0:
            messagebox.showerror(_("Error"), _("API call interval cannot be negative."), parent=self)
            self.api_interval_spinbox.focus_set()
            return False
        if not (1 <= max_concurrent_requests <= 10):
            messagebox.showerror(_("Error"), _("Max concurrent requests must be between 1 and 10."), parent=self)
            self.max_concurrent_requests_spinbox.focus_set()
            return False

        self.app_config["ai_api_key"] = api_key
        self.app_config["ai_api_base_url"] = api_base_url if api_base_url else DEFAULT_API_URL
        self.app_config["ai_target_language"] = target_language
        self.app_config["ai_model_name"] = model_name
        self.app_config["ai_api_interval"] = api_interval
        self.app_config["ai_use_translation_context"] = use_context
        self.app_config["ai_context_neighbors"] = context_neighbors
        self.app_config["ai_use_original_context"] = use_original_context
        self.app_config["ai_original_context_neighbors"] = original_context_neighbors
        self.app_config["ai_max_concurrent_requests"] = max_concurrent_requests

        self.ai_translator_instance.api_key = api_key
        self.ai_translator_instance.model_name = model_name
        self.ai_translator_instance.api_url = api_base_url if api_base_url else DEFAULT_API_URL

        changed = (api_key != self.initial_api_key or
                   api_base_url != self.initial_api_base_url or
                   target_language != self.initial_target_language or
                   model_name != self.initial_model_name or
                   api_interval != self.initial_api_interval or
                   use_context != self.initial_use_context or
                   context_neighbors != self.initial_context_neighbors or
                   use_original_context != self.initial_use_original_context or
                   original_context_neighbors != self.initial_original_context_neighbors or
                   max_concurrent_requests != self.initial_max_concurrent_requests)

        if changed:
            self.save_config_callback()

        return True