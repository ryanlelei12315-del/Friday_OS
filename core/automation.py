from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class DownloadFolderHandler(FileSystemEventHandler):
    def __init__(self, callback_func):
        self.callback = callback_func

    def on_created(self, event):
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if file_path.suffix in [".tmp", ".crdownload", ".part"]:
            return
        self.callback(file_path)


class FridayAutomationManager:
    def __init__(self):
        self.observer = Observer()
        self.scheduler = BackgroundScheduler()

    def handle_new_download(self, file_path: Path):
        print(f"[Automation Engine] New file landed: {file_path.name}")
        # Hook your existing alert/voice notifier logic here later

    def start(self):
        downloads_path = str(Path.home() / "Downloads")
        handler = DownloadFolderHandler(self.handle_new_download)
        self.observer.schedule(handler, downloads_path, recursive=False)
        self.observer.start()
        self.scheduler.start()

    def stop(self):
        self.observer.stop()
        self.observer.join(timeout=1.0)
        self.scheduler.shutdown()
