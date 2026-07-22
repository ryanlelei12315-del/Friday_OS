import json

from pywinauto import Desktop


def click_ui_element(window_title_match: str, element_name: str) -> str:
    """Finds an open window and clicks a specific UI element inside it."""
    try:
        # Attach to the desktop
        desktop = Desktop(backend="uia")
        # Find window containing the match string
        window = desktop.window(title_re=f".*{window_title_match}.*")

        # Locate and click the child element (e.g., button, menu item)
        element = window.child_window(title=element_name, control_type="Button")
        element.click_input()

        return json.dumps({"status": "success", "target": element_name})
    except Exception as e:
        return json.dumps({"status": "failed", "error": str(e)})
