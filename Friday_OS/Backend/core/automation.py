import os
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Import the self-healing entry point directly
from core.local_executor import main as run_local_evolution_loop


class UniversalFolderHandler(FileSystemEventHandler):
    """
    A multi-purpose file observer that handles downloads and workspace hooks together.
    """

    def __init__(self, download_callback, task_callback):
        self.download_callback = download_callback
        self.task_callback = task_callback

    def on_created(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # 1. Maintain original Downloads logic
        if "Downloads" in str(file_path):
            if file_path.suffix in [".tmp", ".crdownload", ".part"]:
                return
            self.download_callback(file_path)

    def on_modified(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # 2. Intercept local workspace tasks instantly when written
        if (
            file_path.name == "friday_tasks.json"
            or file_path.name == "friday_tasks.txt"
        ):
            print(
                f"[Automation Engine] Target updated: {file_path.name}. Awakening Brain-2..."
            )
            self.task_callback()


class FridayAutomationManager:
    def __init__(self):
        self.observer = Observer()
        self.scheduler = BackgroundScheduler()

        # Establish the runtime communication directory
        self.workspace_dir = os.path.expanduser("~/FridayOS_Workspace")
        os.makedirs(self.workspace_dir, exist_ok=True)

    def handle_new_download(self, file_path: Path):
        """Your original working download logic is preserved right here."""
        print(f"[Automation Engine] New file landed: {file_path.name}")

    def start(self):
        # Paths to monitor
        downloads_path = str(Path.home() / "Downloads")

        # Attach our universal callback handler
        handler = UniversalFolderHandler(
            download_callback=self.handle_new_download,
            task_callback=run_local_evolution_loop,
        )

        # Register both folder listeners to the same active background engine loop
        self.observer.schedule(handler, downloads_path, recursive=False)
        self.observer.schedule(handler, self.workspace_dir, recursive=False)

        self.observer.start()
        self.scheduler.start()
        print(f"[Automation Layer Active] Tracking directory: {downloads_path}")
        print(f"[Automation Layer Active] Tracking directory: {self.workspace_dir}")

    def stop(self):
        self.observer.stop()
        self.observer.join(timeout=1.0)
        self.scheduler.shutdown()
