# IMPLEMENTATION ROADMAP: FRIDAY OS

This roadmap lays out a structured, 13-phase engineering sequence to transform FridayOS from a fragile chatbot-with-tools prototype into a production-ready, autonomous Windows computer-use agent.

---

## Roadmap Phases Overview

```
                      PHASE 0: Repository Stabilization
                                    │
                       PHASE 1: Core Agent Runtime
                                    │
                       PHASE 2: Typed Tool System
                                    │
                     PHASE 3: Policy/Security Layer
                                    │
                     PHASE 4: Windows System Control
                                    │
                    PHASE 5: Observation & Verification
                                    │
                      PHASE 6: Planning & Recovery
                                    │
                            PHASE 7: Memory
                                    │
                            PHASE 8: Voice
                                    │
                     PHASE 9: Browser/Computer-Use
                                    │
                   PHASE 10: Device Orchestration
                                    │
                   PHASE 11: Proactive Intelligence
                                    │
                    PHASE 12: Production Hardening
```

---

## Phase Specifications

### PHASE 0: Repository Stabilization
* **Goal**: Clean up dead code, redundant file imports, and establish a green test suite runner.
* **Architectural Change**: Remove duplicate modules, fix eager module-level DB initializations, and establish headless test mocks.
* **Files/Modules Affected**: `Friday_OS/Backend/tools.py` (Deleted), `memory/memory_manager.py` (Refactored to lazy-init), `tests/conftest.py` (Created).
* **Dependencies**: Python standard library, pytest.
* **Implementation Tasks**:
  1. Remove duplicate `tools.py` module from package root.
  2. Implement `conftest.py` with mock structures for pywinauto, pyautogui, and win32gui.
  3. Clean up the database connection so that importing memory modules does not trigger connection errors.
* **Tests**: Run `python -m pytest tests/` and assert 100% green execution.
* **Acceptance Criteria**: All unit tests pass cleanly in headless/Linux and local Windows environments.
* **Risks**: None. Refactoring is non-functional cleanup.
* **Rollback Strategy**: Revert to git commit prior to cleanup.

---

### PHASE 1: Core Agent Runtime
* **Goal**: Replace the single-shot conversational responder with a stateful control loop.
* **Architectural Change**: Introduce the `Orchestrator` engine which manages the agent state transition table.
* **Files/Modules Affected**: Create `core/orchestrator.py`, `core/runtime_state.py`.
* **Dependencies**: Pydantic, asyncio, Phase 0.
* **Implementation Tasks**:
  1. Define the state enum (OBSERVE, PLAN, EXECUTE, VERIFY, REFLECT, COMPLETE).
  2. Implement the `TaskState` schema tracking goals, steps, constraints, and results.
  3. Code the main transition loop managing async transitions.
* **Tests**: Run unit tests on state transitions using mock tools and mock steps.
* **Acceptance Criteria**: Orchestrator can take a goal, step through queue items, execute mock tool calls, and transition cleanly to completion.
* **Risks**: Complex transition conditions could lead to infinite loops.
* **Rollback Strategy**: Disable Orchestrator and bypass state machine back to direct LiveKit calling.

---

### PHASE 2: Typed Tool System
* **Goal**: Refactor Friday tools to be deterministic, typed interfaces.
* **Architectural Change**: Implement the abstract `FridayTool` class with strict schema, timeout, risk level, and output properties.
* **Files/Modules Affected**: Create `tools/base.py`, refactor `tools/tools_files.py`, `tools/tools_apps.py`.
* **Dependencies**: Pydantic validation, Phase 1.
* **Implementation Tasks**:
  1. Write the abstract `FridayTool` class.
  2. Refactor filesystem tools to subclass `FridayTool`, implementing strict Pydantic inputs.
  3. Implement explicit execution timeouts using `asyncio.wait_for()`.
* **Tests**: Test input validation with invalid schemas, asserting validation failures are caught cleanly.
* **Acceptance Criteria**: Tools reject invalid inputs before execution and return structured result formats.
* **Risks**: Refactoring existing tools could break the conversational agent's functional calls.
* **Rollback Strategy**: Maintain a compatibility bridge mapping the new `FridayTool` classes back to standard LiveKit `@function_tool` wrappers.

---

### PHASE 3: Policy / Security Layer
* **Goal**: Protect the host machine by adding safety checks and approval steps.
* **Architectural Change**: Implement a Security Gateway intercepting tool executions based on risk levels.
* **Files/Modules Affected**: Create `security/gateway.py`, `security/policies.py`.
* **Dependencies**: Phase 2.
* **Implementation Tasks**:
  1. Define tool risk categories (LOW, MEDIUM, HIGH, CRITICAL).
  2. Implement the `SecurityGateway` to intercept tool payloads.
  3. Code conversational verbal confirmation triggers for MEDIUM risk tools and GUI gates for HIGH risk tools.
* **Tests**: Mock tool requests for `delete_file` (HIGH risk) and verify the execution suspends until approved.
* **Acceptance Criteria**: No high-risk tools can run without explicit verification/dialog approval.
* **Risks**: Blocking loops could freeze the voice transport thread.
* **Rollback Strategy**: Add a global `BYPASS_SECURITY` flag in development modes to bypass security gates.

---

### PHASE 4: Windows System Control
* **Goal**: Build deep, native system control capabilities.
* **Architectural Change**: Move beyond raw subprocesses. Isolate Windows specific actions behind a unified interface.
* **Files/Modules Affected**: Create `core/windows_control.py`, `tools/tools_win_sys.py`.
* **Dependencies**: `pywin32`, `psutil`, Phase 3.
* **Implementation Tasks**:
  1. Wrap Win32 processes, filesystem, and services controls in a clean interface.
  2. Implement robust process listing, selective process termination, and service status monitors.
  3. Create sandboxed shell command executors enforcing denylists.
* **Tests**: Assert process discovery identifies active Notepad windows.
* **Acceptance Criteria**: Friday can discover, focus, and safely control system processes.
* **Risks**: Access denied errors when querying elevated system processes.
* **Rollback Strategy**: Fallback to standard Python `subprocess.run` with restricted scopes if Win32 APIs fail.

---

### PHASE 5: Observation + Verification
* **Goal**: Ensure Friday never assumes a task succeeded without verification.
* **Architectural Change**: Integrate post-execution assertions inside the Orchestrator loop.
* **Files/Modules Affected**: Create `core/verification.py`, update `core/orchestrator.py`.
* **Dependencies**: Phase 4.
* **Implementation Tasks**:
  1. Implement the `VerificationEngine` with rules mapping tools to target states.
  2. Create active verifiers: check ports for dev servers, query window handles for app launches.
  3. Integrate verification assertions directly into the post-execute loop state.
* **Tests**: Simulate a failed app launch (process doesn't appear) and assert verification catches the failure.
* **Acceptance Criteria**: No step is marked successful unless the target state verification is satisfied.
* **Risks**: Long verification routines could increase overall execution latency.
* **Rollback Strategy**: Disable verification checks or configure them as non-blocking alerts.

---

### PHASE 6: Planning + Recovery
* **Goal**: Build complex multi-step execution plans and self-healing recovery.
* **Architectural Change**: Implement structured JSON decomposition planning and self-healing state handlers.
* **Files/Modules Affected**: Create `core/planner.py`, create `core/self_healing.py`.
* **Dependencies**: Phase 5.
* **Implementation Tasks**:
  1. Implement the JSON task decomposer utilizing strong planning models.
  2. Code the self-healing loop: on verification failure, query LLM for corrective actions, rewrite code, or modify steps.
  3. Implement user escalation triggers when retries are exhausted.
* **Tests**: Run mock execution failures (e.g. port occupied) and verify the agent successfully identifies the blocker, stops the offending process, and recovers.
* **Acceptance Criteria**: Friday can complete multi-step goals, detect obstacles, and dynamically recover.
* **Risks**: Recursive self-healing loops could execute runaway commands.
* **Rollback Strategy**: Cap maximum healing attempts to 3, then force user escalation.

---

### PHASE 7: Memory Consolidation
* **Goal**: Unify the fragmented databases and implement cognitive memory retention policies.
* **Architectural Change**: Integrate Postgres, ChromaDB, and Mem0 under a single unified memory coordinator.
* **Files/Modules Affected**: `memory/memory_manager.py`, `memory/long_term.py`, create `memory/policy.py`.
* **Dependencies**: SQLAlchemy, ChromaDB, Phase 6.
* **Implementation Tasks**:
  1. Remove import-time DB initializations, replacing with clean lazy-initializers.
  2. Implement the memory filter policy sorting high-value facts from session noise.
  3. Integrate semantic vector search and raw database dialogue history under a unified retrieval client.
* **Tests**: Store conversations, assert only high-value user preferences are indexed long-term, and query results.
* **Acceptance Criteria**: Friday recalls user preferences and project-specific facts dynamically without memory drift.
* **Risks**: Bloated database tables or vector search slowdowns.
* **Rollback Strategy**: Bypass complex memory filtering and fallback to simple ChromaDB queries.

---

### PHASE 8: Voice Context Integration
* **Goal**: Inject live operating system context directly into active voice conversations.
* **Architectural Change**: Dynamically re-evaluate and append active window and clipboard state to the LLM system prompt before speech generation.
* **Files/Modules Affected**: `main.py`, `core/tracker.py`.
* **Dependencies**: LiveKit Realtime, Phase 7.
* **Implementation Tasks**:
  1. Wire `AmbientContextTracker`'s context dictionary directly into the active Gemini session's prompt updates.
  2. Implement conversational barge-in overrides and interruption handlers.
  3. Create asynchronous non-blocking voice announcements for long-running tool tasks.
* **Tests**: Verify that copying text to the clipboard instantly makes that text available to Friday's conversational prompt.
* **Acceptance Criteria**: Friday responds to visual and clipboard context in real-time conversation.
* **Risks**: Frequent system prompt updates could increase LLM costs or processing latency.
* **Rollback Strategy**: Fallback to static prompts and query the tracker only when explicitly requested.

---

### PHASE 9: Browser & Computer-Use
* **Goal**: Implement stateful browser control and visual computer use fallbacks.
* **Architectural Change**: Deploy a stateful browser singleton using Playwright, and integrate OCR/VLM visual comprehension tools.
* **Files/Modules Affected**: `browser/browser_service.py` (Fixed), create `tools/tools_vision.py`.
* **Dependencies**: Playwright, Pillow, Phase 8.
* **Implementation Tasks**:
  1. Fix the buggy `stop()` routine in `browser_service.py` to prevent zombie relaunches.
  2. Implement stateful cookie preservation, tab management, and DOM text extractors.
  3. Code screenshot and visual coordinate translation tools utilizing vision-language models.
* **Tests**: Execute a stateful login sequence and assert session persistence across website navigations.
* **Acceptance Criteria**: Friday can browse, read pages, manage tabs, and interact visually with screen UI when APIs fail.
* **Risks**: GUI and coordinate shifts can make visual interactions fragile.
* **Rollback Strategy**: Prioritize the deterministic API hierarchy before using visual/mouse click fallbacks.

---

### PHASE 10: Device Orchestration
* **Goal**: Conduct tasks across registered user devices (laptops, phones, home assistant).
* **Architectural Change**: Introduce WebSocket pairing endpoints and a capability routing registry.
* **Files/Modules Affected**: Create `core/device_router.py`, `api/pairing.py`.
* **Dependencies**: Phase 9.
* **Implementation Tasks**:
  1. Code the device registration database and secure pairing handshake endpoints.
  2. Implement capability routing: map target actions (e.g. sending SMS) to active devices.
  3. Develop lightweight mobile and smart-home device companion agents.
* **Tests**: Register a mock phone device and assert that sending an SMS routes the command to the phone wrapper.
* **Acceptance Criteria**: Friday successfully coordinates actions across multiple active devices based on capability advertisements.
* **Risks**: Local network routing and firewall blocks.
* **Rollback Strategy**: Restrict all operations to the local Windows machine if companion connections drop.

---

### PHASE 11: Proactive Intelligence
* **Goal**: Proactively suggest or execute approved, low-risk actions.
* **Architectural Change**: Deploy a periodic background polling scheduler inside the Orchestrator.
* **Files/Modules Affected**: Create `core/proactive_engine.py`, update `core/orchestrator.py`.
* **Dependencies**: Phase 10.
* **Implementation Tasks**:
  1. Implement resource and state checkers (e.g., low battery, idle servers, missing environment variables).
  2. Code proactive recommendation templates: suggest stop/restart, connect chargers, etc.
  3. Integrate the security gateway to ensure proactive actions never execute silently if they pose high risk.
* **Tests**: Mock low-battery status and verify the agent proactively alerts the user with a recommended action.
* **Acceptance Criteria**: Friday provides timely, non-intrusive, context-aware suggestions without running high-risk commands.
* **Risks**: High frequency of interruptions could annoy users.
* **Rollback Strategy**: Implement quiet hours and configure all proactive actions to be purely passive recommendations.

---

### PHASE 12: Production Hardening
* **Goal**: Build a resilient, installable service ready for distribution.
* **Architectural Change**: Package Friday as a background Windows Service and build an installer script.
* **Files/Modules Affected**: Create `scripts/install.ps1`, create `core/service_daemon.py`.
* **Dependencies**: All preceding phases.
* **Implementation Tasks**:
  1. Build a robust PowerShell installer automating environment configurations and database deployments.
  2. Implement Windows Service wrappers (`win32serviceutil`) to ensure Friday runs on boot.
  3. Clean, compile, and finalize the code structure: remove temporary files, stub files, and test mocks.
* **Tests**: Perform clean-install runs on isolated Windows Sandbox machines.
* **Acceptance Criteria**: Friday successfully installs, runs on system boot, and executes all standard tasks without manual terminal runs.
* **Risks**: Local security policy or antivirus blocks.
* **Rollback Strategy**: Fallback to manual execution scripts if service installation fails.
