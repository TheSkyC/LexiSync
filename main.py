import tkinter as tk
from app import OverwatchLocalizerApp, TkinterDnD

if __name__ == "__main__":
    try:
        if TkinterDnD:
            root = TkinterDnD.Tk()
        else:
            print(
                "Warning: tkinterdnd2 not found. File drag-and-drop will be disabled. Install with: pip install tkinterdnd2-universal")
            root = tk.Tk()

        app = OverwatchLocalizerApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\nApplication exited.")
    except Exception as e:
        import traceback

        print(f"An unexpected error occurred:\n{traceback.format_exc()}")
        # In a real app, you might want to log this to a file.