import threading
import time

import psutil
import pyperclip
import win32gui
import win32process


class AmbientContextTracker:
    def __init__(self):
        self.current_context = {
            "active_window_title": "",
            "active_process_name": "",
            "clipboard_text": "",
        }
        self._running = False

    def get_active_window_info(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            return title, process.name()
        except Exception:
            return "", ""

    def _track_loop(self):
        last_clipboard = ""
        while self._running:
            title, proc_name = self.get_active_window_info()
            self.current_context["active_window_title"] = title
            self.current_context["active_process_name"] = proc_name

            try:
                clip = pyperclip.paste()
                if clip != last_clipboard:
                    self.current_context["clipboard_text"] = clip
                    last_clipboard = clip
            except Exception:
                pass

            time.sleep(0.5)  # Poll every 500ms

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._track_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
