# FridayOS

**An ambient, event-driven operating system layer built over a real-time voice/vision pipeline.** FridayOS continuously monitors your desktop context, watches your filesystem, and presents an always-on voice interface powered by LiveKit, Google Gemini Realtime, and a native Windows API sensor suite.

---

## Key Capabilities

- **Ambient UI Context Tracking** — Background thread polls Win32 API at 500ms intervals to capture the active window title, foreground process name, and live clipboard content without any user intervention.
- **Event-Driven File Automation** — Watchdog filesystem observer watches the `~/Downloads` directory for new file creation events; APScheduler provides a background job execution bus for deferred or recurring automation tasks.
- **Real-time Multi-modal Interface** — LiveKit WebRTC transport delivers low-latency audio input/output and video input (webcam) to a `google.beta.realtime.RealtimeModel` (Gemini Flash), with BVC noise cancellation and a 23-function tool registry spanning file ops, browser control, app lifecycle, smart home, email, weather, web search, and vector memory recall.

---

## Prerequisites & System Constraints

| Requirement | Details |
|-------------|---------|
| **Operating System** | **Windows 10/11 x64 is mandatory.** FridayOS depends on `win32gui`, `win32process`, `os.startfile`, and `pywinauto`, which are Win32-exclusive. |
| **Python** | Python **3.10** or later (3.12 recommended; `__pycache__` targets CPython 3.12) |
| **PostgreSQL** | Local or remote PostgreSQL instance with pgvector extension, accessible from the project environment |
| **LiveKit Access** | LiveKit Server (self-hosted) or LiveKit Cloud account with Room URL, API Key, and API Secret |
| **Google Cloud** | Gemini API key with Realtime API access |
| **Groq API Key** | Optional but used by the structural automation worker for fast background LLM inference |
| **Gmail SMTP** | Optional; required only for the email tool (`GMAIL_USER` + `GMAIL_APP_PASSWORD`) |
| **Home Assistant** | Optional; required only for smart-home entity control (`HOME_ASSISTANT_URL` + `HOME_ASSISTANT_TOKEN`) |
| **Playwright Browsers** | Chrome or Edge must be installed for browser automation tools |

> **Note:** PostgreSQL is required because the memory subsystem uses SQLAlchemy (short-term store) and ChromaDB/pgvector (long-term vector memory). Local vector persistence lives in `./data/chroma/`.

---

## Step-by-Step Installation

### 1. Clone and enter the repository

```powershell
git clone https://github.com/<your-org>/fridayos.git
cd fridayos
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install --upgrade pip
pip install `
  livekit-agents `
  livekit-plugins-openai `
  livekit-plugins-silero `
  livekit-plugins-google `
  livekit-plugins-noise-cancellation `
  mem0ai `
  duckduckgo-search `
  langchain-community `
  requests `
  python-dotenv `
  psutil `
  pyperclip `
  pywin32 `
  watchdog `
  apscheduler `
  aiohttp `
  playwright `
  rapidfuzz `
  pywinauto `
  sqlalchemy `
  psycopg[binary] `
  chromadb `
  langchain-huggingface `
  langchain-postgres `
  groq `
  google-generativeai
```

**Install Playwright browser binaries:**

```powershell
playwright install chromium
```

### 4. Configure environment variables

Create a `.env` file in the project root based on the template below:

```env
# LiveKit (required)
LIVEKIT_URL=https://your-project.livekit.cloud
LIVEKIT_API_KEY=API_xxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxx

# Google Gemini (required)
GOOGLE_API_KEY=AIzaSy...

# Groq backend worker (required)
GROQ_API_KEY=gsk_...

# Gmail SMTP (optional)
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

# Home Assistant (optional)
HOME_ASSISTANT_URL=http://192.168.1.100:8123
HOME_ASSISTANT_TOKEN=eyJ...

# PostgreSQL (required)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=friday_memory
POSTGRES_USER=friday
POSTGRES_PASSWORD=change_this_password
```

### 5. Prepare PostgreSQL

Ensure the `friday_memory` database exists and the role has access:

```sql
CREATE DATABASE friday_memory;
CREATE USER friday WITH PASSWORD 'change_this_password';
GRANT ALL PRIVILEGES ON DATABASE friday_memory TO friday;
```

If using pgvector, enable the extension in the database:

```sql
\c friday_memory
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## Quick-Start Execution Guide

FridayOS's default `python main.py` executes the **LiveKit AgentServer** entry point. This path pre-warms the ambient OS sensors, binds to the LiveKit network layer, and then blocks on the agent server. A voice session begins the instant a participant joins the configured LiveKit room:

```powershell
python main.py
```

This performs the complete boot sequence:

1. **Windows guard check** — exits immediately on non-Windows platforms.
2. **Ambient Context Tracker** — `prewarm_subsystems` spawns a daemon thread that polls `win32gui.GetForegroundWindow()`, `win32process.GetWindowThreadProcessId()`, and `pyperclip.paste()` every 500 ms, populating a shared `current_context` dict.
3. **File Automation Manager** — starts a `watchdog.Observer` on `~/Downloads` and an APScheduler `BackgroundScheduler`.
4. **LiveKit Server** — `cli.run_app(server)` attaches the LiveKit CLI. When a participant joins the room, `rtc_session_entrypoint` creates the `FridayAgent`, which uses a Google Gemini Realtime `Aoede` voice model, BVC noise cancellation, video input, and the full tool registry.
5. **Voice Interaction** — the agent has full read/write access to files, browsers, running apps, Home Assistant devices, email, web search, and vector memory recall.

> **Important:** `main.py` contains four `if __name__ == "__main__"`: blocks at module scope. The first block calls `cli.run_app(server)` and blocks indefinitely. The remaining three blocks are **unreachable dead code** at runtime and will never execute.

### Verified Command Summary

```powershell
# Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install psutil pyperclip pywin32 watchdog apscheduler aiohttp playwright rapidfuzz pywinauto sqlalchemy psycopg[binary] chromadb langchain-huggingface langchain-postgres groq google-generativeai
playwright install chromium

# Database setup (requires running PostgreSQL)
psql -U postgres -c "CREATE DATABASE friday_memory;"

# Run
python main.py
```

---

## Project Structure

```
Live_Kit_Jarvis/
├── main.py                    # LiveKit AgentServer + subsystem boot / shutdown hooks
├── agent.py                   # FridayAgent definition, tool registry, entrypoint
├── prompts.py                 # System prompt, behavior layer, user understanding layer
├── tools.py                   # Legacy top-level tools (weather, web search, email, Groq worker)
├── requirements.txt
├── .env                       # API keys and connection strings (DO NOT COMMIT)
├── app_index.json             # Pre-built Windows application launch index
├── core/
│   ├── tracker.py             # AmbientContextTracker (win32gui + psutil + pyperclip)
│   ├── automation.py          # FridayAutomationManager (watchdog + APScheduler)
│   ├── daemon.py              # Placeholder daemon module
│   └── scheduler.py           # Placeholder scheduler module
├── pipeline/
│   └── livekit_client.py      # LiveKit pipeline context synchronizer
├── tools/
│   ├── tools.py               # Core tool implementations duplicated from root tools.py
│   ├── tools_apps.py          # Windows application lifecycle (open/close/list/index)
│   ├── tools_browser.py       # Playwright-based browser control (open/google/read)
│   ├── tools_files.py         # File system manipulation (CRUD + find)
│   ├── tools_memory.py        # Vector memory recall via ChromaDB
│   └── home_assistant_tools.py # Home Assistant device control (turn on/off/toggle/state)
├── memory/
│   ├── __init__.py            # initialize_memory() → SQLAlchemy table creation
│   ├── database.py            # SQLAlchemy engine/session factory (PostgreSQL/psycopg)
│   ├── short_term.py          # Conversation ORM model
│   ├── store.py               # Interaction storage helper
│   ├── long_term.py           # ChromaDB persistent collection wrapper
│   └── memory_manager.py      # mem0 Memory configuration
├── browser/
│   ├── browser_manager.py     # Playwright singleton lifecycle
│   ├── browser_service.py     # Shared browser instance (Chrome/Edge channel)
│   ├── browser_tools.py       # LangChain-tool wrappers over browser_service
│   ├── browser_state.py       # Simple browser state tracking class
│   └── web_research.py        # Web research module (currently empty)
├── mcp/
│   └── mcp/
│       ├── server.py          # FastMCP server (filesystem tools + PowerShell exec)
│       └── tools/
│           ├── system_ui.py   # UI automation stub (currently empty)
│           ├── file_ops.py    # File ops stub (currently empty)
│           └── search.py      # pywinauto-based UI element click helper
└── test/
    ├── test_db.py             # LangChain + PGVector integration smoke test
    └── test_mem0.py           # mem0 client search/add smoke test
```

---

## Security Note

The `.env` file contains secrets and is excluded from version control. Never commit real credentials. Rotate any keys that may have been exposed in past commits. The project currently contains hard-coded API key values in `tools/tools.py` for the Groq automation worker — migrate these to environment variables immediately.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `sys.platform != "win32"` exit immediately | Run on Windows. WSL2 is unsupported because `win32gui` and `pywinauto` require a native Windows desktop session. |
| `ImportError: No module named 'win32gui'` | Run `pip install pywin32` while the virtual environment is active. |
| PostgreSQL connection refused | Start the PostgreSQL service (`pg_ctl start` or `Start-Service postgresql`) and verify `localhost:5432` is reachable. |
| Playwright browser launch fails | Run `playwright install chromium` and ensure Chrome/Edge is installed. |
| LiveKit room refuses connection | Verify `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` are correct and the server is reachable from your network. |
