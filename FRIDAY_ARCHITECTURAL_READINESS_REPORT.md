# FRIDAY OS: ARCHITECTURAL READINESS REPORT

This readiness report provides a brutally honest, engineering-first, and evidence-based evaluation of FridayOS. It assesses the current codebase and provides an actionable blueprint to transform the project into a genuinely autonomous, reliable, and secure Windows computer-use agent.

---

## 1. What is FRIDAY today?
Today, FridayOS is a **disconnected prototype**. It consists of three primary, uncoordinated layers:
1. **The Voice Interface**: A LiveKit Agent Server that acts as a simple conversational chatbot utilizing Google Gemini Realtime.
2. **The Local PyAutoGUI Loop**: A standalone script (`local_executor.py`) that utilizes Ollama to write and execute python-based UI macro files, with screenshots and tracebacks on failures.
3. **The Web Bridge**: A FastAPI websocket endpoint (`core/app.py`) designed to stream simulated telemetry back to an Electron/Expo mockup.

These layers operate independently, resulting in a system with limited actual autonomy.

---

## 2. What parts are genuinely working?
* **Duplex Audio Streaming**: The LiveKit connection, voice transport, and BVC noise-cancellation pipeline are fully functional.
* **Basic Tool Actions**: Filesystem operations (`tools_files.py`), Start Menu fuzzy application indexing (`tools_apps.py`), and smart-home controls (`home_assistant_tools.py`) operate reliably when invoked in isolation.
* **RAG Document Ingestion**: The sentence-boundary chunker and ChromaDB collection logic (`core/friday_rag.py`) successfully parse and index files for local keyword/semantic search.
* **Primitive Self-Healing**: The pyautogui script generator (`local_executor.py`) successfully uses local Ollama to write, execute, and retry scripts.

---

## 3. What parts are prototypes?
* **The Telemetry Web Bridge**: `/ws/bridge` is a complete mockup that simulates processing latency and returns hardcoded parameters (`"llm_ttft": "2300ms"`).
* **MCP Integration**: The FastMCP server in `mcp/mcp/server.py` is isolated and entirely unused by the active LiveKit voice loop.
* **The Context Tracker**: The tracker thread successfully polls win32 foreground window handles and clipboard strings. However, this is a prototype because **the captured context is never injected** into active conversational sessions—the agent is conversational but blind.

---

## 4. What parts are misleadingly named as capabilities but don't exist?
* **Autonomous Reasoning / Orchestration**: The prompt describes Friday as capable of goal decomposition, state observation, and self-healing. In reality, the main voice agent is a standard, single-shot chatbot. It has **no internal state machine, goal tracking, or verification checks**.
* **Mem0 Memory Integration**: While `memory/memory_manager.py` claims to integrate Mem0 with pgvector, it uses hardcoded localhost credentials, crashes on import, and is completely unused by the active LiveKit agent.

---

## 5. What must be rewritten?
* **The Entire Agent Loop**: Replace the passive conversational responder with a stateful, Observe-Plan-Act-Verify-Reflect orchestrator.
* **The Tool Registration Stack**: Enforce strict base class constraints: Pydantic schemas, explicit execution timeouts, risk-level classifications, and confirmation gateways.
* **Stateful Browser Automation**: Consolidate the parallel browser stacks into a single, stateful Playwright singleton sharing cookies and session states.

---

## 6. What can be preserved?
* **LiveKit WebRTC Integration**: The streaming, turn-taking, and audio transport configurations in `main.py` are solid and should be preserved.
* **The Context Tracker sensor definitions**: The polling routines in `core/tracker.py` are reliable Windows sensors and should be wired into prompt injection.
* **The RAG Chunking Logic**: The line-aware coding chunker and narrative sentence splitters in `core/friday_rag.py` work beautifully.

---

## 7. What is the highest-risk architectural problem?
**Unrestricted Execution Authority (No Security Boundaries)**: Any LLM hallucination or rogue prompt injection can execute destructive file deletions or run arbitrary terminal commands silently. The system has zero permission gates or confirmation dialogs.

---

## 8. What is the highest-value improvement?
**Wiring the Active Context Tracker**: Feeding the output of `AmbientContextTracker` directly into active conversational prompts. This instantly gives Friday "sight"—it will dynamically recognize what files, directories, or applications the user is focused on, transforming it into a context-aware assistant.

---

## 9. What is the FIRST implementation milestone?
**Context-Aware Voice Control (The "Sight" Milestone)**: Update LiveKit's active session system prompt dynamically whenever the user's active window focus or system clipboard text shifts.

---

## 10. What exact acceptance test proves that milestone is complete?
1. Start the LiveKit voice agent.
2. Focus on an active Notepad window containing a coding project.
3. Verbally ask: "Friday, what file am I focused on right now?"
4. **Success criteria**: Friday immediately answers with the exact file title and directory context without executing any manual tools.

---

## Brutal Honest Readiness Scorecard

* **Current Implementation Readiness**: **2.0 / 10**
  *(A collection of loose, fragile prototype modules and stubs).*
* **Architectural Foundation**: **3.0 / 10**
  *(Disconnected blocks, parallel drifting browsers, lack of unified orchestrator).*
* **Path to Real Autonomous Agent**: **9.0 / 10**
  *(With the proposed 13-phase modular roadmap, the transition is highly achievable and technically sound).*
