import tkinter as tk
from tkinter import ttk, simpledialog, scrolledtext, messagebox
import threading
from services.ai_translator import AITranslator
from utils import constants


class AISettingsDialog(simpledialog.Dialog):
    def __init__(self, parent, title, config_manager, ai_translator_ref):
        self.config_manager = config_manager
        self.ai_translator_instance = ai_translator_ref
        self.config = self.config_manager.config
        super().__init__(parent, title)

    def body(self, master):
        master.columnconfigure(1, weight=1)

        api_frame = ttk.LabelFrame(master, text="API Config", padding=(10, 5))
        api_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        api_frame.columnconfigure(1, weight=1)

        ttk.Label(api_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.api_key_var = tk.StringVar(value=self.config.get("ai_api_key", ""))
        self.api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, show="*", width=60)
        self.api_key_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=3)

        ttk.Label(api_frame, text="API Base URL:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        self.api_base_url_var = tk.StringVar(value=self.config.get("ai_api_base_url", constants.DEFAULT_API_URL))
        self.api_base_url_entry = ttk.Entry(api_frame, textvariable=self.api_base_url_var, width=60)
        self.api_base_url_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=3)

        ttk.Label(api_frame, text="Model Name:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=3)
        self.model_name_var = tk.StringVar(value=self.config.get("ai_model_name", "deepseek-chat"))
        self.model_name_entry = ttk.Entry(api_frame, textvariable=self.model_name_var, width=60)
        self.model_name_entry.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=3)

        trans_frame = ttk.LabelFrame(master, text="Translation Settings", padding=(10, 5))
        trans_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        trans_frame.columnconfigure(1, weight=1)

        ttk.Label(trans_frame, text="Target Language:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.target_language_var = tk.StringVar(value=self.config.get("ai_target_language", "中文"))
        self.target_language_entry = ttk.Entry(trans_frame, textvariable=self.target_language_var, width=60)
        self.target_language_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=3)

        ttk.Label(trans_frame, text="API Call Interval (ms):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        self.api_interval_var = tk.IntVar(value=self.config.get("ai_api_interval", 200))
        self.api_interval_spinbox = tk.Spinbox(trans_frame, from_=0, to=10000, increment=50,
                                               textvariable=self.api_interval_var, width=10)
        self.api_interval_spinbox.grid(row=1, column=1, sticky=tk.W, padx=5, pady=3)

        ttk.Label(trans_frame, text="Max Concurrent Requests:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=3)
        self.max_concurrent_requests_var = tk.IntVar(value=self.config.get("ai_max_concurrent_requests", 1))
        self.max_concurrent_requests_spinbox = tk.Spinbox(trans_frame, from_=1, to=10, increment=1,
                                                          textvariable=self.max_concurrent_requests_var, width=10)
        self.max_concurrent_requests_spinbox.grid(row=2, column=1, sticky=tk.W, padx=5, pady=3)

        self.use_context_var = tk.BooleanVar(value=self.config.get("ai_use_translation_context", True))
        self.use_context_check = ttk.Checkbutton(trans_frame, text="Use translated context",
                                                 variable=self.use_context_var, command=self.toggle_context_spinners)
        self.use_context_check.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        self.context_neighbors_var = tk.IntVar(value=self.config.get("ai_context_neighbors", 3))
        self.context_neighbors_spinbox = tk.Spinbox(trans_frame, from_=0, to=10, increment=1,
                                                    textvariable=self.context_neighbors_var, width=5)
        self.context_neighbors_spinbox.grid(row=4, column=1, sticky=tk.W, padx=5, pady=3)
        ttk.Label(trans_frame, text="Translated context neighbors (0=all):").grid(row=4, column=0, sticky=tk.W, padx=25)

        self.use_orig_context_var = tk.BooleanVar(value=self.config.get("ai_use_original_context", True))
        self.use_orig_context_check = ttk.Checkbutton(trans_frame, text="Use original untranslated context",
                                                      variable=self.use_orig_context_var,
                                                      command=self.toggle_context_spinners)
        self.use_orig_context_check.grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        self.orig_context_neighbors_var = tk.IntVar(value=self.config.get("ai_original_context_neighbors", 3))
        self.orig_context_neighbors_spinbox = tk.Spinbox(trans_frame, from_=0, to=10, increment=1,
                                                         textvariable=self.orig_context_neighbors_var, width=5)
        self.orig_context_neighbors_spinbox.grid(row=6, column=1, sticky=tk.W, padx=5, pady=3)
        ttk.Label(trans_frame, text="Original context neighbors (0=all):").grid(row=6, column=0, sticky=tk.W, padx=25)

        prompt_frame = ttk.LabelFrame(master, text="AI Prompt Template", padding=(10, 5))
        prompt_frame.grid(row=2, column=0, columnspan=2, sticky=tk.NSEW, padx=5, pady=5)
        prompt_frame.columnconfigure(0, weight=1)
        prompt_frame.rowconfigure(0, weight=1)

        self.ai_prompt_template_text = scrolledtext.ScrolledText(prompt_frame, height=10, width=70, wrap=tk.WORD,
                                                                 relief=tk.SOLID, borderwidth=1)
        self.ai_prompt_template_text.insert(tk.END,
                                            self.config.get("ai_prompt_template", constants.DEFAULT_AI_PROMPT_TEMPLATE))
        self.ai_prompt_template_text.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        self.test_status_label = ttk.Label(master, text="", wraplength=550)
        self.test_status_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(5, 10))

        master.rowconfigure(2, weight=1)
        self.toggle_context_spinners()
        return self.api_key_entry

    def toggle_context_spinners(self):
        self.context_neighbors_spinbox.config(state=tk.NORMAL if self.use_context_var.get() else tk.DISABLED)
        self.orig_context_neighbors_spinbox.config(state=tk.NORMAL if self.use_orig_context_var.get() else tk.DISABLED)

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="Test Connection", width=15, command=self.test_api_connection_dialog).pack(side=tk.LEFT,
                                                                                                        padx=5, pady=5)
        ttk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="Cancel", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.cancel())
        box.pack()

    def test_api_connection_dialog(self):
        self.test_status_label.config(text="Testing...")
        self.update_idletasks()
        api_key = self.api_key_var.get()
        if not api_key:
            messagebox.showerror("Test Failed", "API Key is required.", parent=self)
            self.test_status_label.config(text="Test Failed: API Key is required.")
            return

        temp_translator = AITranslator(api_key, self.model_name_var.get(), self.api_base_url_var.get())

        def _test_in_thread():
            success, message = temp_translator.test_connection(
                system_prompt_template=self.ai_prompt_template_text.get("1.0", tk.END).strip()
            )
            self.after(0, self._show_test_result, success, message)

        threading.Thread(target=_test_in_thread, daemon=True).start()

    def _show_test_result(self, success, message):
        if self.winfo_exists():
            self.test_status_label.config(text=message)
            messagebox.showinfo("Connection Test", message, parent=self)

    def apply(self):
        self.config["ai_api_key"] = self.api_key_var.get()
        self.config["ai_api_base_url"] = self.api_base_url_var.get().strip() or constants.DEFAULT_API_URL
        self.config["ai_target_language"] = self.target_language_var.get().strip()
        self.config["ai_model_name"] = self.model_name_var.get().strip()
        self.config["ai_api_interval"] = self.api_interval_var.get()
        self.config["ai_prompt_template"] = self.ai_prompt_template_text.get("1.0", tk.END).strip()
        self.config["ai_use_translation_context"] = self.use_context_var.get()
        self.config["ai_context_neighbors"] = self.context_neighbors_var.get()
        self.config["ai_use_original_context"] = self.use_orig_context_var.get()
        self.config["ai_original_context_neighbors"] = self.orig_context_neighbors_var.get()
        self.config["ai_max_concurrent_requests"] = self.max_concurrent_requests_var.get()

        self.config_manager.save_config()

        self.ai_translator_instance.api_key = self.config["ai_api_key"]
        self.ai_translator_instance.model_name = self.config["ai_model_name"]
        self.ai_translator_instance.api_url = self.config["ai_api_base_url"]