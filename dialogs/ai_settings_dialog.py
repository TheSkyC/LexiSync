import tkinter as tk
from tkinter import ttk, simpledialog, scrolledtext, messagebox
import threading
from services.ai_translator import AITranslator
from utils.constants import DEFAULT_AI_PROMPT_TEMPLATE, DEFAULT_API_URL

class AISettingsDialog(simpledialog.Dialog):
    def __init__(self, parent, title, app_config_ref, save_config_callback, ai_translator_ref):
        self.app_config = app_config_ref
        self.save_config_callback = save_config_callback
        self.ai_translator_instance = ai_translator_ref

        self.initial_api_key = self.app_config.get("ai_api_key", "")
        self.initial_api_base_url = self.app_config.get("ai_api_base_url", DEFAULT_API_URL)
        self.initial_target_language = self.app_config.get("ai_target_language", "中文")
        self.initial_api_interval = self.app_config.get("ai_api_interval", 200)
        self.initial_model_name = self.app_config.get("ai_model_name", "deepseek-chat")
        self.initial_prompt_template = self.app_config.get("ai_prompt_template", DEFAULT_AI_PROMPT_TEMPLATE)
        self.initial_use_context = self.app_config.get("ai_use_translation_context", False)
        self.initial_context_neighbors = self.app_config.get("ai_context_neighbors", 0)
        self.initial_use_original_context = self.app_config.get("ai_use_original_context", True)
        self.initial_original_context_neighbors = self.app_config.get("ai_original_context_neighbors", 3)
        self.initial_max_concurrent_requests = self.app_config.get("ai_max_concurrent_requests", 1)
        super().__init__(parent, title)

    def body(self, master):
        master.columnconfigure(1, weight=1)
        api_frame = ttk.LabelFrame(master, text="API 配置", padding=(10, 5))
        api_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        api_frame.columnconfigure(1, weight=1)

        # ... (API Key, Base URL, Model Name entries remain the same) ...
        api_row_idx = 0
        ttk.Label(api_frame, text="API Key:").grid(row=api_row_idx, column=0, sticky=tk.W, padx=5, pady=3)
        self.api_key_var = tk.StringVar(value=self.initial_api_key)
        self.api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, show="*", width=60)
        self.api_key_entry.grid(row=api_row_idx, column=1, sticky=tk.EW, padx=5, pady=3)
        api_row_idx += 1

        ttk.Label(api_frame, text="API Base URL:").grid(row=api_row_idx, column=0, sticky=tk.W, padx=5, pady=3)
        self.api_base_url_var = tk.StringVar(value=self.initial_api_base_url)
        self.api_base_url_entry = ttk.Entry(api_frame, textvariable=self.api_base_url_var, width=60)
        self.api_base_url_entry.grid(row=api_row_idx, column=1, sticky=tk.EW, padx=5, pady=3)
        api_row_idx += 1

        ttk.Label(api_frame, text="模型名称:").grid(row=api_row_idx, column=0, sticky=tk.W, padx=5, pady=3)
        self.model_name_var = tk.StringVar(value=self.initial_model_name)
        self.model_name_entry = ttk.Entry(api_frame, textvariable=self.model_name_var, width=60)
        self.model_name_entry.grid(row=api_row_idx, column=1, sticky=tk.EW, padx=5, pady=3)


        trans_frame = ttk.LabelFrame(master, text="翻译设置", padding=(10, 5))
        trans_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        trans_frame.columnconfigure(1, weight=1)

        trans_row_idx = 0
        # ... (Target Language, API Interval, Max Concurrency entries remain the same) ...
        ttk.Label(trans_frame, text="目标语言:").grid(row=trans_row_idx, column=0, sticky=tk.W, padx=5, pady=3)
        self.target_language_var = tk.StringVar(value=self.initial_target_language)
        self.target_language_entry = ttk.Entry(trans_frame, textvariable=self.target_language_var, width=60)
        self.target_language_entry.grid(row=trans_row_idx, column=1, sticky=tk.EW, padx=5, pady=3)
        trans_row_idx += 1

        ttk.Label(trans_frame, text="API 调用间隔 (ms):").grid(row=trans_row_idx, column=0, sticky=tk.W, padx=5, pady=3)
        self.api_interval_var = tk.IntVar(value=self.initial_api_interval)
        self.api_interval_spinbox = tk.Spinbox(trans_frame, from_=0, to=10000, increment=50,
                                               textvariable=self.api_interval_var, width=10)
        self.api_interval_spinbox.grid(row=trans_row_idx, column=1, sticky=tk.W, padx=5, pady=3)
        trans_row_idx += 1

        ttk.Label(trans_frame, text="最大并发请求数:").grid(row=trans_row_idx, column=0, sticky=tk.W, padx=5, pady=3)
        self.max_concurrent_requests_var = tk.IntVar(value=self.initial_max_concurrent_requests)
        self.max_concurrent_requests_spinbox = tk.Spinbox(trans_frame, from_=1, to=10, increment=1,
                                                          textvariable=self.max_concurrent_requests_var, width=10)
        self.max_concurrent_requests_spinbox.grid(row=trans_row_idx, column=1, sticky=tk.W, padx=5, pady=3)
        trans_row_idx += 1

        # --- Original Text Context ---
        self.use_original_context_var = tk.BooleanVar(value=self.initial_use_original_context)
        self.use_original_context_check = ttk.Checkbutton(trans_frame, text="引用临近原文作为上下文",
                                                 variable=self.use_original_context_var,
                                                 command=self.toggle_context_neighbors_state)
        self.use_original_context_check.grid(row=trans_row_idx, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5,0))
        trans_row_idx += 1

        original_context_neighbor_frame = ttk.Frame(trans_frame)
        original_context_neighbor_frame.grid(row=trans_row_idx, column=0, columnspan=2, sticky=tk.W, padx=25)
        ttk.Label(original_context_neighbor_frame, text="引用临近").pack(side=tk.LEFT)
        self.original_context_neighbors_var = tk.IntVar(value=self.initial_original_context_neighbors)
        self.original_context_neighbors_spinbox = tk.Spinbox(original_context_neighbor_frame, from_=0, to=10, increment=1,
                                                    textvariable=self.original_context_neighbors_var, width=5)
        self.original_context_neighbors_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(original_context_neighbor_frame, text="条原文 (0为所有)").pack(side=tk.LEFT)
        trans_row_idx += 1

        # --- Translated Text Context ---
        self.use_context_var = tk.BooleanVar(value=self.initial_use_context)
        self.use_context_check = ttk.Checkbutton(trans_frame, text="引用临近译文作为上下文",
                                                 variable=self.use_context_var,
                                                 command=self.toggle_context_neighbors_state)
        self.use_context_check.grid(row=trans_row_idx, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5,0))
        trans_row_idx += 1

        context_neighbor_frame = ttk.Frame(trans_frame)
        context_neighbor_frame.grid(row=trans_row_idx, column=0, columnspan=2, sticky=tk.W, padx=25)
        ttk.Label(context_neighbor_frame, text="引用临近").pack(side=tk.LEFT)
        self.context_neighbors_var = tk.IntVar(value=self.initial_context_neighbors)
        self.context_neighbors_spinbox = tk.Spinbox(context_neighbor_frame, from_=0, to=10, increment=1,
                                                    textvariable=self.context_neighbors_var, width=5)
        self.context_neighbors_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(context_neighbor_frame, text="条翻译 (0为所有)").pack(side=tk.LEFT)
        trans_row_idx += 1

        # ... (Prompt Frame and Test Status Label remain the same) ...
        prompt_frame = ttk.LabelFrame(master, text="AI 提示词模板", padding=(10, 5))
        prompt_frame.grid(row=2, column=0, columnspan=2, sticky=tk.NSEW, padx=5, pady=5)
        prompt_frame.columnconfigure(0, weight=1)
        prompt_frame.rowconfigure(0, weight=1)

        self.ai_prompt_template_text = scrolledtext.ScrolledText(prompt_frame, height=10, width=70, wrap=tk.WORD,
                                                                 relief=tk.SOLID, borderwidth=1)
        self.ai_prompt_template_text.insert(tk.END, self.initial_prompt_template)
        self.ai_prompt_template_text.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        ttk.Label(prompt_frame, text="可用占位符: [Target Language], [Untranslated Context], [Translated Context], [Custom Translate]").grid(
            row=1, column=0,
            sticky=tk.W, padx=5,
            pady=(2, 5))

        self.test_status_label = ttk.Label(master, text="", wraplength=550)
        self.test_status_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(5, 10))

        master.rowconfigure(2, weight=1)
        self.toggle_context_neighbors_state()
        return self.api_key_entry

    def toggle_context_neighbors_state(self):
        trans_state = tk.NORMAL if self.use_context_var.get() else tk.DISABLED
        self.context_neighbors_spinbox.config(state=trans_state)

        orig_state = tk.NORMAL if self.use_original_context_var.get() else tk.DISABLED
        self.original_context_neighbors_spinbox.config(state=orig_state)

    def buttonbox(self):
        box = ttk.Frame(self)

        test_btn = ttk.Button(box, text="测试连接", width=10, command=self.test_api_connection_dialog)
        test_btn.pack(side=tk.LEFT, padx=5, pady=5)

        ok_btn = ttk.Button(box, text="确定", width=10, command=self.ok, default=tk.ACTIVE)
        ok_btn.pack(side=tk.LEFT, padx=5, pady=5)
        cancel_btn = ttk.Button(box, text="取消", width=10, command=self.cancel)
        cancel_btn.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.cancel())

        box.pack()

    def test_api_connection_dialog(self):
        self.test_status_label.config(text="测试中...")
        self.update_idletasks()

        api_key = self.api_key_var.get()
        api_url = self.api_base_url_var.get().strip() or DEFAULT_API_URL
        model_name = self.model_name_var.get().strip()

        if not api_key:
            messagebox.showerror("测试失败", "API Key 未填写。", parent=self)
            self.test_status_label.config(text="测试失败: API Key 未填写。")
            return

        temp_translator = AITranslator(api_key, model_name, api_url)

        def _test_in_thread():
            success, message = temp_translator.test_connection(
                system_prompt_template=self.ai_prompt_template_text.get("1.0", tk.END).strip()
            )
            self.after(0, self._show_test_result, success, message)

        threading.Thread(target=_test_in_thread, daemon=True).start()

    def _show_test_result(self, success, message):
        if self.winfo_exists():
            self.test_status_label.config(text=message)
            if success:
                messagebox.showinfo("测试连接", message, parent=self)
            else:
                messagebox.showerror("测试连接", message, parent=self)

    def apply(self):
        # ... (This method needs to be updated to save the new settings) ...
        api_key = self.api_key_var.get()
        api_base_url = self.api_base_url_var.get().strip()
        target_language = self.target_language_var.get().strip()
        model_name = self.model_name_var.get().strip()
        api_interval = self.api_interval_var.get()
        prompt_template = self.ai_prompt_template_text.get("1.0", tk.END).strip()
        use_context = self.use_context_var.get()
        context_neighbors = self.context_neighbors_var.get()
        use_original_context = self.use_original_context_var.get()
        original_context_neighbors = self.original_context_neighbors_var.get()
        max_concurrent_requests = self.max_concurrent_requests_var.get()

        # ... (Validation remains the same) ...
        if not target_language:
            messagebox.showerror("错误", "目标语言不能为空。", parent=self)
            self.target_language_entry.focus_set()
            return
        if not model_name:
            messagebox.showerror("错误", "模型名称不能为空。", parent=self)
            self.model_name_entry.focus_set()
            return
        if api_interval < 0:
            messagebox.showerror("错误", "API 调用间隔不能为负。", parent=self)
            self.api_interval_spinbox.focus_set()
            return
        if not prompt_template:
            messagebox.showerror("错误", "AI 翻译提示词模板不能为空。", parent=self)
            self.ai_prompt_template_text.focus_set()
            return
        if not (1 <= max_concurrent_requests <= 10):
            messagebox.showerror("错误", "最大并发请求数必须在 1 到 10 之间。", parent=self)
            self.max_concurrent_requests_spinbox.focus_set()
            return

        self.app_config["ai_api_key"] = api_key
        self.app_config["ai_api_base_url"] = api_base_url if api_base_url else DEFAULT_API_URL
        self.app_config["ai_target_language"] = target_language
        self.app_config["ai_model_name"] = model_name
        self.app_config["ai_api_interval"] = api_interval
        self.app_config["ai_prompt_template"] = prompt_template
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
                   prompt_template != self.initial_prompt_template or
                   use_context != self.initial_use_context or
                   context_neighbors != self.initial_context_neighbors or
                   use_original_context != self.initial_use_original_context or
                   original_context_neighbors != self.initial_original_context_neighbors or
                   max_concurrent_requests != self.initial_max_concurrent_requests)

        if changed:
            self.save_config_callback()