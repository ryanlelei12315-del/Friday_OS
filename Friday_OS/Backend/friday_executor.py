import pyautogui
import time

def execute_task():
    # Step 1: Open Notepad
    pyautogui.press('win')  # Press Windows key to open Start menu
    time.sleep(0.5)  # Wait for the Start menu to appear
    pyautogui.typewrite('notepad')  # Type 'notepad' in the search bar
    time.sleep(1)  # Wait for Notepad to appear in the results
    pyautogui.press('enter')  # Press Enter to open Notepad

    # Step 2: Type text in Notepad
    time.sleep(0.5)  # Wait for Notepad to focus
    pyautogui.typewrite('FridayOS Core Subsystems Online.')  # Type the specified text

    # Step 3: Minimize window
    time.sleep(1)  # Wait for typing to complete
    pyautogui.press('win')  # Press Windows key + D to minimize all windows

if __name__ == '__main__':
    execute_task()