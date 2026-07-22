# FridayOS — Technical Architecture & Developer Guide

This document provides a complete, line-by-line-accurate specification of FridayOS internals for engineers who need to extend, debug, or replicate the system from scratch.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Module Inventory & Responsibilities](#module-inventory--responsibilities)
3. [Async Control Flow & Boot Sequence](#async-control-flow--boot-sequence)
4. [Subsystem Deep Dives](#subsystem-deep-dives)
   - 4.1 [Ambient Context Tracker](#41-ambient-context-tracker)
   - 4.2 [File Automation Manager](#42-file-automation-manager)
   - 4.3 [LiveKit Agent Pipeline](#43-livekit-agent-pipeline)
   - 4.4 [Memory Subsystem](#44-memory-subsystem)
   - 4.5 [Browser Automation](#45-browser-automation)
   - 4.6 [MCP Server Layer](#46-mcp-server-layer)
5. [Tool Registry Reference](#tool-registry-reference)
6. [Environment Variables Reference](#environment-variables-reference)
7. [Data Flow Diagrams](#data-flow-diagrams)
8. [Known Issues & Technical Debt](#known-issues--technical-debt)
9. [Extending the System](#extending-the-system)
10. [Testing & Validation](#testing--validation)

---

## 1. System Overview

FridayOS is a **Win32-native, event-driven Python application** that sits between a user's desktop and a cloud-hosted LLM voice pipeline. It has three primary runtime dimensions:

- **Synchronous background thread** — polls OS sensors at 500 ms intervals.
- **Asynchronous asyncio event loop** — runs the LiveKit agent session, VoIP transport, and database/SDK I/O.
- **Filesystem events + scheduler** — Watchdog `Observer` threads and APScheduler jobs react to disk activity outside the main loop.

All three dimensions feed into a single shared mutable state object (`AmbientContextTracker.current_context`), which is read by the voice agent at inference time to inject live desktop context into the system prompt.

---

## 2. Module Inventory & Responsibilities

| Module | Type | Responsibility |
|--------|------|----------------|
| `main.py` | Async orchestrator | LiveKit AgentServer boot, prewarm hooks, graceful shutdown. Contains four `if __name__ == "__main__"` guards; only the first is reachable at runtime. |
| `agent.py` | Agent definition | `FridayAgent` (LiveKit `Agent` subclass), 23 `@function_tool` registrations, session start with video/audio/noise cancellation options. |
| `prompts.py` | Static text | Personality prompt, behavior rules, user-understanding layer, welcome message constants. |
| `core/tracker.py` | Threaded sensor | Foreground window title, process name, clipboard text via `win32gui`, `win32process`, `psutil`, `pyperclip`. |
| `core/automation.py` | Watchdog + Scheduler | `FridayAutomationManager`: `watchdog.Observer` on `~/Downloads`, `APScheduler.BackgroundScheduler`. |
| `core/daemon.py` | Placeholder | Empty module (0 lines). Intended as future system daemon abstraction. |
| `core/scheduler.py` | Placeholder | Empty module (0 lines). |
| `pipeline/livekit_client.py` | Pipeline helper | `start_livekit_pipeline(context_tracker)` builds a dynamic system instruction string from live OS state. Currently does not establish a real LiveKit connection; prints a stub. |
| `tools/tools.py` | Tool implementations | `structural_automation_worker` (Groq), `get_weather`, `search_web` (DuckDuckGo), `send_email` (Gmail SMTP). |
| `tools/tools_apps.py` | Windows app lifecycle | App index builder, fuzzy matcher (`rapidfuzz`), `open_application`, `list_running_apps`, `is_app_running`, `close_application` (protected-process safe). |
| `tools/tools_browser.py` | Browser automation | `open_website`, `google_search`, `read_website` via `playwright.async_api`. |
| `tools/tools_files.py` | File system | `list_files`, `find_file`, `create_file`, `read_file`, `move_file`, `delete_file`. |
| `tools/tools_memory.py` | Memory retrieval | `recall_memory`, `extract_memory` — thin wrappers over `memory.long_term.search_memory`. |
| `tools/home_assistant_tools.py` | Smart-home bridge | `turn_on_device`, `turn_off_device`, `toggle_device`, `get_device_state` via `automation.home_assistant.HomeAssistantClient`. |
| `memory/__init__.py` | Initialization | `initialize_memory()` calls `Base.metadata.create_all(bind=engine)`. |
| `memory/database.py` | ORM layer | SQLAlchemy engine + sessionmaker using `DATABASE_URL` from env (PostgreSQL + psycopg). |
| `memory/short_term.py` | ORM model | `Conversation` table: `id`, `user_message`, `assistant_response`, `timestamp`. |
| `memory/store.py` | Helper | `store_interaction(user_message, assistant_response)` formats and calls `save_memory`. |
| `memory/long_term.py` | Vector store | `chromadb.PersistentClient` at `./data/chroma/` with collection `friday_memory`. `save_memory`, `search_memory`. |
| `memory/memory_manager.py` | Memory client | `mem0.Memory` configured for `pgvector` provider. |
| `browser/browser_manager.py` | Singleton lifecycle | `BrowserManager` starts/stops a shared Playwright + Chromium instance. |
| `browser/browser_service.py` | Shared browser | `BrowserService` manages a single `playwright.chromium.lash(channel="chrome")` (with Edge fallback). **Note:** `stop()` attempts to relaunch, which is a bug. |
| `browser/browser_tools.py` | LangChain tools | LangChain `@tool` decorators wrapping `browser_service`. |
| `browser/browser_state.py` | State bag | Simple class tracking `current_url`, `open_tabs`, `last_search`, `browsing_history`. |
| `browser/web_research.py` | Stub | Empty module. |
| `mcp/mcp/server.py` | FastMCP | MCP server `"FridayOS_Core"` with tools: `list_directory`, `read_text_file`, `execute_powershell`, `search_desktop_files`, `interact_with_application`. **Note:** contains duplicate `if __name__ == "__main__"` block and duplicate `FastMCP("filesystem")` initialization. |
| `mcp/mcp/tools/search.py` | UI automation | `fast_local_search` and `click_ui_element` using `pywinauto.Desktop` (`backend="uia"`). |
| `mcp/mcp/tools/system_ui.py` | Stub | Empty module. |
| `mcp/mcp/tools/file_ops.py` | Stub | Empty module. |
| `test/test_db.py` | Integration test | Validates LangChain + HuggingFace embeddings + PGVector against local PostgreSQL. |
| `test/test_mem0.py` | Integration test | Validates mem0 client add + search flow. |

---

## 3. Async Control Flow & Boot Sequence

### Default LiveKit Boot Path (`main.py` → `cli.run_app(server)`)

```
cli.run_app(server)
  │
  ├─ prewarm_subsystems(server)
  │     ├─ AmbientContextTracker.start()
  │     │     └─ daemon thread polls win32gui + psutil + pyperclip every 500ms
  │     └─ FridayAutomationManager.start()
  │           ├─ watchdog.Observer on ~/Downloads
  │           └─ APScheduler.BackgroundScheduler.start()
  │
  └─ LiveKit CLI runs AgentServer indefinitely
        └─ For every room participant:
              rtc_session_entrypoint(JobContext)
                └─ await entrypoint(ctx, context_tracker=tracker)
                      ├─ AgentSession.start(
                      │     room=ctx.room,
                      │     agent=FridayAgent(),
                      │     room_options=RoomOptions(
                      │         video_input=VideoInputOptions(),
                      │         audio_input=AudioInputOptions(
                      │             noise_cancellation=BVC())
                      │     )
                      │ )
                      ├─ ctx.connect()
                      └─ session.generate_reply(WELCOME_MESSAGE)
```

> **Critical:** `main.py` defines **four** `if __name__ == "__main__":` blocks at module scope (lines 51, 106, 132, 168). The **first** block calls `cli.run_app(server)` and **blocks indefinitely**. The remaining three blocks (`asyncio.run(run_friday_os())`, `asyncio.run(main())`, `asyncio.run(run_os_agent())`) are **unreachable dead code** at runtime.

### Legacy / Unreachable Path: `run_os_agent()`

```
asyncio.run(run_os_agent())
  │
  1. tracker = AmbientContextTracker()
     tracker.start()
  2. automation = FridayAutomationManager()
     automation.start()
  3. await start_livekit_pipeline(context_tracker=tracker)
     └─ builds dynamic system instructions from tracker state
        (stub: does not yet connect to a LiveKit room)
  4. while True: await asyncio.sleep(1)
```

This path is **never reached** because it appears after the blocking `cli.run_app(server)` call in the first `__main__` guard.

### Threading Model Summary

| Thread / Task | Kind | What it does |
|---------------|------|--------------|
| Main thread | asyncio event loop | LiveKit agent session, room connection, tool execution context |
| `_track_loop` | `threading.Thread` (daemon) | Polls Win32 API + pyperclip every 500 ms |
| Watchdog observer | `watchdog.observers.Observer` thread | Filesystem event callbacks on `~/Downloads` |
| APScheduler | background thread pool | Scheduled job execution |

> **Concurrency note:** The tracker thread writes to `current_context` without locks. Reads in the async tool context (`context_tracker.current_context`) are lock-free as well. This is safe for a dict of simple strings under CPython's GIL, but becomes a data-race risk if the dict grows to nested mutable objects.

---

## 4. Subsystem Deep Dives

### 4.1 Ambient Context Tracker

**File:** `core/tracker.py`

The tracker is a class that exposes a `current_context` dict:

```python
{
    "active_window_title": str,
    "active_process_name": str,
    "clipboard_text": str,
}
```

**Polling loop (`_track_loop`):**

```
Every 500ms:
  win32gui.GetForegroundWindow() ──► hwnd
  win32gui.GetWindowText(hwnd) ──► title
  win32process.GetWindowThreadProcessId(hwnd) ──► pid
  psutil.Process(pid).name() ──► proc_name
  pyperclip.paste() ──► clipboard
  Update self.current_context
```

**Dependencies:**
- `pywin32` → `win32gui`, `win32process`
- `psutil`
- `pyperclip`

**Start/stop contract:**
- `start()` sets `_running = True` and spawns the daemon thread.
- `stop()` sets `_running = False`. The daemon thread exits on its next loop iteration. No `join()` is called; the thread is killed implicitly when the process exits.

**Edge cases:**
- `win32gui.GetForegroundWindow()` may return an invalid handle during desktop switches or UAC prompts; wrapped in `try/except` returning empty strings.
- `pyperclip.paste()` can fail on headless sessions or restricted clipboard permissions; silently caught.

### 4.2 File Automation Manager

**File:** `core/automation.py`

Two distinct automation primitives:

#### Watchdog Observer (Filesystem Events)

- Watches `Path.home() / "Downloads"` (non-recursive).
- `DownloadFolderHandler.on_created` fires for every new file.
- Ignores incomplete downloads (`.tmp`, `.crdownload`, `.part`).
- Calls `handle_new_download(file_path)` — currently a `print()` stub.

#### APScheduler Background Scheduler

- Instantiated as `BackgroundScheduler` but no jobs are added.
- `start()` / `stop()` lifecycle aligned with the Observer.

**Start/stop contract:**
- `start()` → observer.start() + scheduler.start().
- `stop()` → observer.stop() + observer.join(timeout=1.0) + scheduler.shutdown().

### 4.3 LiveKit Agent Pipeline

**File:** `agent.py`

#### FridayAgent

Extends `livekit.agents.Agent`. Constructor does the following:

1. Calls `initialize_memory()` to ensure PostgreSQL tables exist.
2. Passes combined instructions to `Agent`:
   ```
   FRIDAY_SYSTEM_PROMPT
   USER_UNDERSTANDING_LAYER
   FRIDAY_BEHAVIOR
   ```
3. Configures LLM as `google.beta.realtime.RealtimeModel`:
   - Voice preset: `Aoede`
   - Temperature: `0.7`
4. Registers 23 `@function_tool`-decorated callables.

#### entrypoint

```python
async def entrypoint(ctx: JobContext, context_tracker=None):
```

- Reads live OS context.
- Defines `get_live_system_prompt()` which returns a dynamic string synthesizing `active_window_title`, `active_process_name`, and `clipboard_text`. This string is **not automatically injected** into the agent's system prompt by the framework; instead, it is available for tool-level consumption or future session reconfiguration.
- Starts an `AgentSession` with:
  - `room=ctx.room`
  - `room_io.RoomOptions(video_input=..., audio_input=noise_cancellation.BVC())`
- Calls `ctx.connect()`.
- Generates a phonetic welcome reply.

**Important:** `get_live_system_prompt()` is defined inside `entrypoint` but is never passed to `session.generate_reply()` or similar. The live context is currently only logged, not injected into the model at inference time. This is a gap between the design intent and implementation.

### 4.4 Memory Subsystem

FridayOS uses three overlapping memory backends:

#### SQLAlchemy Short-Term Store
- **File:** `memory/database.py`, `memory/short_term.py`
- PostgreSQL connection via `psycopg` binary driver.
- `DATABASE_URL` constructed from env vars.
- `Conversation` ORM table stores raw user/assistant message pairs.

#### ChromaDB Long-Term Vector Store
- **File:** `memory/long_term.py`
- Persistent client at `./data/chroma/`.
- Collection name: `friday_memory`.
- `save_memory(text)` → `collection.add(documents=[text], ids=[hash(text)])`.
- `search_memory(query)` → top-5 semantic search.

#### mem0 Cloud Client
- **File:** `memory/memory_manager.py`
- Configured for `pgvector` provider but instantiates `Memory.from_config()`. The config specifies `postgresql+psycopg://` credentials. `memory.initialize()` is called eagerly at import time.
- **Note:** This will attempt to connect to PostgreSQL on import, which can cause import-time failures if the DB is down.

**Memory flow:**
```
User speaks ► Agent responds ► store_interaction() ► save_memory() ► ChromaDB
                  │
                  └─► recall_memory() tool ► search_memory() ► ChromaDB results
```

### 4.5 Browser Automation

Two parallel browser automation stacks exist:

#### Playwright Direct (`tools/tools_browser.py`)
- Each call creates a fresh `async_playwright()` context, launches Chromium, executes, then closes.
- Risk: heavy per-call overhead and orphaned browser processes if exceptions prevent cleanup.

#### BrowserService Singleton (`browser/`)
- `BrowserService.start()` launches a single Chromium instance (`channel="chrome"`, `headless=False`).
- `BrowserManager` exposes `start()` / `stop()`.
- `BrowserState` tracks URLs and tab state in a plain Python class (not thread-safe).
- **Bug in `browser_service.py`:** The `stop()` method contains a `try/except` block that attempts to re-launch the browser inside cleanup, which is unintended.

### 4.6 MCP Server Layer

**File:** `mcp/mcp/server.py`

- Uses `FastMCP("FridayOS_Core")`.
- Exposes tools via `@mcp.tool()` decorator:
  - `list_directory(path)` — `Path.iterdir()`
  - `read_text_file(path)` — `Path.read_text()`
  - `execute_powershell(command)` — `subprocess.run(["powershell", "-Command", command])`
  - `search_desktop_files(query)` — delegates to `fast_local_search`
  - `interact_with_application(window_title, button_name)` — delegates to `click_ui_element`

**Issue:** The file contains two `if __name__ == "__main__":` blocks and two `mcp = FastMCP(...)` initializations (one for `"filesystem"`, one for `"FridayOS_Core"`). Only the last `mcp = FastMCP("FridayOS_Core")` binding is active; the first is overwritten.

**UI Automation (`mcp/mcp/tools/search.py`):**
- `click_ui_element(window_title_match, element_name)`:
  1. `pywinauto.Desktop(backend="uia")`
  2. Regex match window title
  3. Find child button by name
  4. `element.click_input()`

---

## 5. Tool Registry Reference

FridayAgent registers the following tools at construction:

| Tool | File | Purpose |
|------|------|---------|
| `get_weather` | `tools/tools.py` | `wttr.in/{city}?format=3` HTTP GET |
| `search_web` | `tools/tools.py` | DuckDuckGo via `langchain_community.tools.DuckDuckGoSearchRun` |
| `send_email` | `tools/tools.py` | Gmail SMTP via `smtplib.SMTP("smtp.gmail.com:587")` |
| `recall_memory` | `tools/tools_memory.py` | ChromaDB semantic search top-5 |
| `structural_automation_worker` | `tools/tools.py` | Delegates to Groq `llama-3.3-70b-versitile` for background text processing |
| `list_files` | `tools/tools_files.py` | `Path.iterdir()` on a given directory |
| `find_file` | `tools/tools_files.py` | Recursive filename substring search from `C:/Users` |
| `create_file` | `tools/tools_files.py` | `Path.write_text()` with parent directory creation |
| `read_file` | `tools/tools_files.py` | `Path.read_text()`, capped at 5,000 chars |
| `move_file` | `tools/tools_files.py` | `shutil.move()` |
| `delete_file` | `tools/tools_files.py` | `Path.unlink()` |
| `refresh_app_index` | `tools/tools_apps.py` | Rebuilds `app_index.json` by scanning Start Menu, Program Files, Desktop |
| `list_running_apps` | `tools/tools_apps.py` | `psutil.process_iter(["name"])`, sorted, capped at 300 |
| `open_application` | `tools/tools_apps.py` | Fuzzy match against `app_index.json` + `os.startfile()` |
| `close_application` | `tools/tools_apps.py` | `proc.kill()` skipping protected system processes |
| `is_app_running` | `tools/tools_apps.py` | Substring match process name |
| `open_website` | `tools/tools_browser.py` | Playwright `chromium.launch(headless=False)` |
| `google_search` | `tools/tools_browser.py` | Playwright Google search, returns raw HTML truncated to 5,000 chars |
| `read_website` | `tools/tools_browser.py` | Playwright `page.text_content("body")`, truncated to 10,000 chars |
| `turn_on_device` | `tools/home_assistant_tools.py` | HA REST call `{domain}.turn_on` |
| `turn_off_device` | `tools/home_assistant_tools.py` | HA REST call `{domain}.turn_off` |
| `toggle_device` | `tools/home_assistant_tools.py` | HA REST call `{domain}.toggle` |
| `get_device_state` | `tools/home_assistant_tools.py` | HA REST GET `/api/states/{entity_id}` |

---

## 6. Environment Variables Reference

| Variable | Required | Used By | Purpose |
|----------|----------|---------|---------|
| `LIVEKIT_URL` | **Yes** | `agent.py` via LiveKit SDK | WebSocket URL for room connection |
| `LIVEKIT_API_KEY` | **Yes** | `agent.py` via LiveKit SDK | LiveKit project credential |
| `LIVEKIT_API_SECRET` | **Yes** | `agent.py` via LiveKit SDK | LiveKit signing secret |
| `GOOGLE_API_KEY` | **Yes** | `agent.py` via `livekit.plugins.google` | Gemini Realtime API access |
| `GROQ_API_KEY` | **Yes** | `tools/tools.py` | Groq LLM backend for automation worker |
| `GMAIL_USER` | No | `tools/tools.py` | SMTP sender identity |
| `GMAIL_APP_PASSWORD` | No | `tools/tools.py` | Gmail app-password for SMTP auth |
| `HOME_ASSISTANT_URL` | No | `automation/home_assistant.py` | HA instance base URL |
| `HOME_ASSISTANT_TOKEN` | No | `automation/home_assistant.py` | HA long-lived access token |
| `POSTGRES_HOST` | **Yes** | `memory/database.py` | PostgreSQL host |
| `POSTGRES_PORT` | **Yes** | `memory/database.py` | PostgreSQL port |
| `POSTGRES_DB` | **Yes** | `memory/database.py` | Database name |
| `POSTGRES_USER` | **Yes** | `memory/database.py` | Database username |
| `POSTGRES_PASSWORD` | **Yes** | `memory/database.py` | Database password |

**Security:** `tools/tools.py` lines 24–26 contain a **hard-coded Groq API key fallback** in the `api_key` argument. This must be removed for production.

---

## 7. Data Flow Diagrams

### Live Audio/Video Round Trip

```
User Voice ──► LiveKit Room (WebRTC) ──► AgentSession
                                         │
                                         ├─ BVC Noise Cancellation
                                         ├─ Google Gemini Realtime (Aoede voice)
                                         │
                                         ├─ System Prompt (static prompts.py)
                                         │
                                         ├─ Live Context Injection (planned, not wired)
                                         │   └─ AmbientContextTracker.current_context
                                         │       ├─ active_window_title
                                         │       ├─ active_process_name
                                         │       └─ clipboard_text
                                         │
                                          └─ Tool Execution (23 tools)
                                             ├─ File ops       ──► Disk
                                             ├─ Browser        ──► Playwright / Chrome
                                             ├─ App lifecycle  ──► psutil / os.startfile()
                                             ├─ Smart Home     ──► Home Assistant REST
                                             ├─ Email          ──► SMTP
                                             ├─ Web Search     ──► DuckDuckGo
                                             ├─ Weather        ──► wttr.in
                                             └─ Memory recall  ──► ChromaDB / PGVector
```

### Filesystem Event Path

```
File created in ~/Downloads
  │
  ├─ Watchdog Observer thread detects FS event
  │   └─ DownloadFolderHandler.on_created(event)
  │       ├─ Skip if directory
  │       ├─ Skip if .tmp / .crdownload / .part
  │       └─ FridayAutomationManager.handle_new_download(path)
  │           └─ print("[Automation Engine] New file landed: ...")
  │
  └─ (Future hook: voice announcement, auto-sort, HA trigger, etc.)
```

### Memory Write/Read Path

```
Write path:
  Agent interaction ──► store_interaction(user_msg, assistant_resp)
                       └─ save_memory(chunk)
                           └─ chromadb.collection.add()

Read path:
  Agent calls recall_memory(query)
    └─ search_memory(query)
        └─ chromadb.collection.query(query_texts=[query], n_results=5)
            └─ str(results) returned to agent as tool response
```

---

## 8. Known Issues & Technical Debt

1. **`main.py` syntactic fragility** — The file contains **four** distinct `if __name__ == "__main__"` blocks (lines 51, 106, 132, 168). The **first** block calls `cli.run_app(server)` and blocks indefinitely. The remaining three (`run_friday_os()`, `main()`, `run_os_agent()`) are **unreachable dead code** at runtime. Only four separate `if` guards exist.
2. **Duplicate `tools.py`** — `tools.py` at the project root and `tools/tools.py` in the package contain near-identical code (weather, search, email, Groq worker). The root `tools.py` is not imported by `agent.py`, which uses the package version, making the root file dead code.
3. **Live context not injected** — `get_live_system_prompt()` is defined inside `entrypoint()` in `agent.py:99-109` but never appended to or used to modify the agent's system prompt. The live OS state is printed to console but not fed to the model.
4. **Hard-coded API key** — `tools/tools.py:24-26` contains an inline Groq API key string in the `api_key=os.environ.get(...)` fallback. This is a critical security issue because the secret is committed to the repository history.
5. **`browser_service.stop()` bug** — `browser/browser_service.py:37-48` wraps a relaunch attempt inside `stop()`, meaning cleanup may spawn a new browser process.
6. **Empty modules** — `core/daemon.py`, `core/scheduler.py`, `browser/web_research.py`, `mcp/mcp/tools/system_ui.py`, and `mcp/mcp/tools/file_ops.py` are all zero-length placeholders.
7. **Lock-free shared dict** — `current_context` is read/written across the daemon thread and the asyncio main loop without synchronization. Stable under CPython's GIL for simple string values, but not a robust cross-interpreter pattern.
8. **`memory_manager.py` eager import** — `mem0.Memory.from_config(...)` runs at module import time, causing PostgreSQL connection attempts even if the memory paths are unused.
9. **`app_index.json` machine-specific** — The shipped `app_index.json` contains absolute `C:\Users\ryanl\...` paths. Any other user must rebuild it via `refresh_app_index`.
10. **MCP server dual initialization** — `mcp/mcp/server.py` initializes `FastMCP("filesystem")` and then immediately overwrites it with `FastMCP("FridayOS_Core")`. The first binding is dead code.

---

## 9. Extending the System

### Adding a New Tool

1. Create a module under `tools/` (e.g., `my_tool.py`).
2. Import `function_tool` and `RunContext` from `livekit.agents`.
3. Decorate an `async def` with `@function_tool()`.
4. Import and register in `agent.py`'s `FridayAgent.__init__()` tools list.

### Adding a Background Sensor

1. Inherit from `threading.Thread` or use an `asyncio.Task`.
2. Write updates to `AmbientContextTracker.current_context` or a new shared state object.
3. Start in `main.py`'s boot sequence before the LiveKit loop begins.

### Replacing the Memory Backend

1. Implement `save_memory(text)` and `search_memory(query, n_results=5)`.
2. Update `tools/tools_memory.py` to import from your new module.
3. Remove or bypass `memory_manager.py` if meg0 is not desired.

### Migrating Hard-Coded Secrets

Replace `tools/tools.py:24-26`:

```python
# Before (insecure)
api_key = os.environ.get(
    "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"
),
# After (secure)
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY is not set")
```

---

## 10. Testing & Validation

### Runtime Verification Checklist

- [ ] `python main.py` prints `====== FRIDAY OS MASTER BOOT SEQUENCE ======` and both subsystem ready messages.
- [ ] Switching active windows updates `current_context["active_window_title"]` (verify via logging or `print`).
- [ ] Copying text to clipboard updates `current_context["clipboard_text"]`.
- [ ] Dropping a `.pdf` into `~/Downloads` triggers `[Automation Engine] New file landed: ...`.
- [ ] `python -c "from memory import initialize_memory; initialize_memory()"` creates tables without error.
- [ ] `recall_memory("test query")` returns a non-empty string.

### Existing Test Scripts

| Script | What it validates |
|--------|-------------------|
| `test/test_db.py` | Loads `HuggingFaceEmbeddings`, connects to PGVector, adds a document, runs semantic search. |
| `test/test_mem0.py` | Adds a two-message conversation to mem0 and queries by user name. |

### Playwright / Browser Integration Test

```powershell
python -c "
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://example.com')
        print(await page.title())
        await browser.close()

asyncio.run(test())
"
```

### LiveKit Connection Test

```powershell
python -c "
import asyncio
from livekit import rtc
# Replace with real values from .env
url = 'wss://your-project.livekit.cloud'
token = '<user-jwt>'
async def test():
    room = rtc.Room()
    await room.connect(url, token)
    print('Connected:', room.sid)
    await room.disconnect()
asyncio.run(test())
"
```

---

## 11. Platform Compatibility Matrix

| Component | Windows | WSL2 | macOS | Linux |
|-----------|---------|------|-------|-------|
| AmbientContextTracker | ✅ Native | ❌ No `win32gui` | ❌ | ❌ |
| FridayAutomationManager | ✅ Native | ⚠️ Limited (GUI events fail) | ✅ | ✅ |
| `os.startfile()` | ✅ Native | ⚠️ Depends on GUI forwarding | ❌ | ❌ |
| LiveKit Agent | ✅ Any | ✅ Any | ✅ Any | ✅ Any |
| Playwright browser automation | ✅ Chrome/Edge | ✅ Chrome/Edge | ✅ Chrome | ✅ Chrome |
| PostgreSQL backend | ✅ Any | ✅ Any | ✅ Any | ✅ Any |

**Conclusion:** The core OS-sensor layer is Windows-only. The LiveKit agent, file tools, web tools, and memory tools can run on macOS/Linux if the Win32-dependent modules are stubbed out.

---

*End of technical specification.*
