import json
import os
import time

WORKSPACE_DIR = os.path.expanduser("~/FridayOS_Workspace")
os.makedirs(WORKSPACE_DIR, exist_ok=True)


def inject_test_task():
    task_payload = {
        "pending_task": "Open notepad and type 'FridayOS Core Subsystems Online.' then minimize the window.",
        "status": "queued",
        "timestamp": time.time(),
    }

    target_path = os.path.join(WORKSPACE_DIR, "friday_tasks.json")

    print("[*] Injecting autonomous objective into data bridge workspace...")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(task_payload, f, indent=4)
    print("[✔] Task written safely. Check your main FridayOS terminal!")


if __name__ == "__main__":
    inject_test_task()
