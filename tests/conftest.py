import sys
from unittest.mock import MagicMock

# Mock platform-dependent and X11 display-dependent modules
MOCK_MODULES = [
    "pyautogui",
    "pygetwindow",
    "pywinauto",
    "win32gui",
    "win32process",
    "pyperclip",
]

for mod in MOCK_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
