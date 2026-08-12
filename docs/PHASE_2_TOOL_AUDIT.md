# Phase 2 — Existing Tool Audit

This document details the audit of all existing tools in the FridayOS repository. Every tool is classified and assigned an architectural action to fit within our new safe, typed, permission-aware, and verified Tool Registry.

---

## Existing Tool Classification Matrix

| Existing Tool | Location | Current Interface | Problems | Target Interface | Action |
|:---|:---|:---|:---|:---|:---:|
| `structural_automation_worker` | `tools/tools.py` | `(user_request: str) -> str` | Direct call to Groq; lacks schema validation or timeouts. | `structural_automation_worker` | **ADAPT** |
| `get_weather` | `tools/tools.py` | `(city: str) -> str` | Synchronous HTTP request with no async integration. | `weather.get` | **ADAPT** |
| `search_web` | `tools/tools.py` | `(query: str) -> str` | Synchronous langchain DuckDuckGo tool wrapper. | `web.search` | **ADAPT** |
| `send_email` | `tools/tools.py` | `(to_email: str, subject: str, message: str) -> str` | Uses synchronous smtplib; blocks event loop. | `email.send` | **REFACTOR** |
| `recall_memory` | `tools/tools_memory.py` | `(query: str) -> str` | Direct ChromaDB search wrapping; untyped. | `memory.recall` | **ADAPT** |
| `extract_memory` | `tools/tools_memory.py` | `(transcript: str) -> str` | Redundant wrapper around same long term search. | `memory.recall` | **REMOVE** |
| `refresh_app_index` | `tools/tools_apps.py` | `() -> str` | Sync directory scans; blocks execution thread. | `application.refresh_index` | **ADAPT** |
| `open_application` | `tools/tools_apps.py` | `(app_name: str) -> str` | Fuzzy matches and runs `os.startfile` blindly; no verification. | `application.launch` | **REPLACE** |
| `list_running_apps` | `tools/tools_apps.py` | `() -> str` | Direct psutil scan returned as single string list. | `process.list` or `application.list` | **REPLACE** |
| `is_app_running` | `tools/tools_apps.py` | `(app_name: str) -> str` | String matching loop over process lists; redundant. | `process.list` | **REMOVE** |
| `close_application` | `tools/tools_apps.py` | `(app_name: str) -> str` | Kills process blindly by substring match; high risk. | `process.terminate` | **REFACTOR** |
| `open_website` | `tools/tools_browser.py` | `(url: str) -> str` | Non-persistent browser instance; synchronous. | `browser.open` | **REPLACE** |
| `google_search` | `tools/tools_browser.py` | `(query: str) -> str` | Hardcoded search scraping with heavy browser launch. | `web.search` or `browser.search` | **REPLACE** |
| `read_website` | `tools/tools_browser.py` | `(url: str) -> str` | Separate heavy launch to grab text; slow. | `browser.read_page` | **REPLACE** |
| `list_files` | `tools/tools_files.py` | `(directory: str) -> str` | Returns unformatted text; lacks pagination or checks. | `filesystem.list` | **REPLACE** |
| `find_file` | `tools/tools_files.py` | `(filename: str, root_directory: str) -> str` | Brittle recursion over disk drives; blocks thread. | `filesystem.find` | **ADAPT** |
| `create_file` | `tools/tools_files.py` | `(file_path: str, content: str) -> str` | Overwrites files silently without directory filters. | `filesystem.write` | **REPLACE** |
| `read_file` | `tools/tools_files.py` | `(file_path: str) -> str` | Flat read capped at 5k chars with no pagination. | `filesystem.read` | **REPLACE** |
| `move_file` | `tools/tools_files.py` | `(source: str, destination: str) -> str` | Overwrites files silently; unmonitored. | `filesystem.move` | **ADAPT** |
| `delete_file` | `tools/tools_files.py` | `(file_path: str) -> str` | Destructive file unlinking with zero confirmation gates. | `filesystem.delete` | **REPLACE** |
| `turn_on_device` | `tools/home_assistant_tools.py` | `(entity_id: str) -> str` | Straight REST integration with no schemas. | `iot.device_on` | **ADAPT** |
| `turn_off_device` | `tools/home_assistant_tools.py` | `(entity_id: str) -> str` | REST post wrapping. | `iot.device_off` | **ADAPT** |
| `toggle_device` | `tools/home_assistant_tools.py` | `(entity_id: str) -> str` | REST post wrapping. | `iot.device_toggle` | **ADAPT** |
| `get_device_state` | `tools/home_assistant_tools.py` | `(entity_id: str) -> str` | REST state fetch. | `iot.device_status` | **ADAPT** |
| `list_directory` | `mcp/.../server.py` | `(path: str) -> str` | Redundant filesystem listing inside FastMCP. | `filesystem.list` | **REMOVE** |
| `read_text_file` | `mcp/.../server.py` | `(path: str) -> str` | Redundant file reading inside FastMCP. | `filesystem.read` | **REMOVE** |
| `execute_powershell` | `mcp/.../server.py` | `(command: str) -> str` | High-risk arbitrary execution with no policy check. | `terminal.execute` | **REPLACE** |
| `search_desktop_files` | `mcp/.../server.py` | `(query: str) -> str` | Fast scan utilizing pywinauto index; dead stub. | `filesystem.find` | **REMOVE** |
| `interact_with_application` | `mcp/.../server.py` | `(window_title: str, button_name: str) -> str` | Complex pywinauto GUI element manipulation stub. | `window.interact` | **REFACTOR** |

---

## Key Refactoring Goals for Phase 2

1. **Safety Isolation**: High-risk tools like file deletions, process terminations, and terminal execution MUST go through the new `PolicyEngine` pre-check prior to execution.
2. **Determinism over Brittleness**: Application launches must fuzzy-match against configured system directories and verify the process starts instead of invoking raw terminal actions or guessing.
3. **Structured Results**: Replace arbitrary logging strings with structured `ToolResult` schemas representing status blocks (`SUCCESS`, `FAILED`, `TIMEOUT`, etc.) so the orchestrator can take intelligent fallback steps.
