import tkinter as tk
from tkinter import ttk, simpledialog


class StatisticsDialog(simpledialog.Dialog):
    def __init__(self, parent, title, translatable_objects):
        self.objects = translatable_objects
        super().__init__(parent, title)

    def body(self, master):
        total = len(self.objects)
        translated = sum(1 for obj in self.objects if obj.translation.strip() and not obj.is_ignored)
        untranslated = sum(1 for obj in self.objects if not obj.translation.strip() and not obj.is_ignored)
        ignored = sum(1 for obj in self.objects if obj.is_ignored)
        reviewed = sum(1 for obj in self.objects if obj.is_reviewed and not obj.is_ignored)

        total_chars = sum(len(obj.original_semantic) for obj in self.objects if not obj.is_ignored)
        translated_chars = sum(
            len(obj.original_semantic) for obj in self.objects if obj.translation.strip() and not obj.is_ignored)

        stats_frame = ttk.Frame(master, padding=10)
        stats_frame.pack(fill=tk.BOTH, expand=True)

        # --- Text Stats ---
        text_stats_frame = ttk.LabelFrame(stats_frame, text="Counts", padding=10)
        text_stats_frame.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')

        stats = [
            ("Total Strings:", total),
            ("Translated:", translated),
            ("Untranslated:", untranslated),
            ("Ignored:", ignored),
            ("Reviewed:", reviewed),
            ("Total Characters (translatable):", f"{total_chars:,}"),
            ("Translated Characters:", f"{translated_chars:,}")
        ]

        for i, (label, value) in enumerate(stats):
            ttk.Label(text_stats_frame, text=label, font=('Segoe UI', 10, 'bold')).grid(row=i, column=0, sticky='w',
                                                                                        padx=5, pady=2)
            ttk.Label(text_stats_frame, text=str(value)).grid(row=i, column=1, sticky='e', padx=5, pady=2)

        # --- Chart ---
        chart_frame = ttk.LabelFrame(stats_frame, text="Progress", padding=10)
        chart_frame.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')

        self.canvas = tk.Canvas(chart_frame, width=300, height=200, bg='white')
        self.canvas.pack()

        self.draw_bar_chart(total, translated, reviewed)

        stats_frame.columnconfigure(1, weight=1)
        return stats_frame

    def draw_bar_chart(self, total, translated, reviewed):
        canvas = self.canvas
        width = 300
        height = 180

        if total == 0:
            canvas.create_text(width / 2, height / 2, text="No data to display")
            return

        # Translation Progress Bar
        trans_percent = translated / (total - sum(1 for o in self.objects if o.is_ignored)) if (total - sum(
            1 for o in self.objects if o.is_ignored)) > 0 else 0
        bar_width = (width - 40) * trans_percent
        canvas.create_rectangle(20, 40, 20 + bar_width, 70, fill='green', outline='darkgreen')
        canvas.create_rectangle(20 + bar_width, 40, width - 20, 70, fill='#E0E0E0', outline='grey')
        canvas.create_text(width / 2, 55, text=f"Translated: {trans_percent:.1%}")
        canvas.create_text(20, 25, text="Translation Progress", anchor='w')

        # Review Progress Bar
        review_percent = reviewed / translated if translated > 0 else 0
        bar_width = (width - 40) * review_percent
        canvas.create_rectangle(20, 120, 20 + bar_width, 150, fill='blue', outline='darkblue')
        canvas.create_rectangle(20 + bar_width, 120, width - 20, 150, fill='#E0E0E0', outline='grey')
        canvas.create_text(width / 2, 135, text=f"Reviewed: {review_percent:.1%}")
        canvas.create_text(20, 105, text="Review Progress (of translated)", anchor='w')

    def buttonbox(self):
        box = ttk.Frame(self)
        ok_btn = ttk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE)
        ok_btn.pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.ok)
        box.pack()