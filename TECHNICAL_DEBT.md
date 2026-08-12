# TECHNICAL DEBT & CODE SMELL CATALOG: FRIDAY OS

This document catalogs the technical debt, syntactic vulnerabilities, and code smells discovered in the FridayOS repository. We classify them into priority tiers and recommend concrete engineering fixes.

---

## 1. Technical Debt Classification Matrix

| Priority | Location | Problem | Why It Matters / Impact | Recommended Fix | Dependency |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **CRITICAL** | `tools/tools.py:24-26` | Hardcoded fallback Groq API key in git history. | **Security Vulnerability**: Secret is committed to repository version control. | Purge key using `git-filter-repo` and enforce strict `.env` loading. | None |
| **CRITICAL** | `main.py` & `agent.py` | Overlapping prompt blocks. Context tracker state is **not injected** into active voice sessions. | **Broken Core Feature**: Friday is conversational but entirely blind to desktop window state. | Inject active context into Gemini Realtime system prompt updates dynamically. | None |
| **CRITICAL** | `memory/memory_manager.py` | Eager DB initializations with hardcoded credentials at import-time. | **System Stability**: App crash-loops on import if database is down or credentials differ. | Implement lazy-initialization wrappers inside an explicit `initialize()` function. | Phase 0 |
| **HIGH** | `Friday_OS/Backend/tools.py` | Redundant duplicate of package module `tools/tools.py` causing naming conflicts. | **Build Blocker**: Pytest fails out of the box due to Python module/package namespace collision. | Delete redundant root file (Completed). | Phase 0 |
| **HIGH** | `tools/tools.py:101-125` | Resource leak: SMTP connection established **before** checking environment credentials. | **Resource Wastage**: Opens a Google connection and initiates TLS even if GMAIL_USER is missing. | Verify environment credentials before opening the socket connection (Completed). | Phase 0 |
| **HIGH** | `browser/browser_service.py` | Buggy `stop()` method attempts to re-launch browser processes during cleanup. | **Resource Leak**: Cleanup leaks Chromium zombie tasks, eventually consuming all system RAM. | Refactor `stop()` to cleanly close Playwright and browser processes without relaunches. | Phase 9 |
| **HIGH** | `mcp/mcp/server.py` | Parallel FastMCP server initializes `"filesystem"`, overwrites with `"FridayOS_Core"`. | **Dead Code / Complexity**: Double main blocks and overlapping initializations. | Clean up duplicate initializations and merge into a single active FastMCP instance. | Phase 12 |
| **MEDIUM** | `core/daemon.py`, `core/scheduler.py` | Zero-length empty placeholder modules. | **Maintenance Complexity**: Clutters repository structure with dead files. | Remove empty modules; replace with proper implementation packages. | Phase 12 |
| **MEDIUM** | `tools/tools_browser.py` vs `browser_service.py` | Drifting parallel browser automation stacks (stateless vs stateful). | **Resource Wastage / Complexity**: Double dependencies. Playwright tools are slow and don't share sessions. | Unify tools to use the stateful Browser Service singleton. | Phase 9 |
| **LOW** | `app_index.json` | Hardcoded machine-specific absolute file paths (`C:\Users\ryanl`). | **Portability Blocker**: Application fuzzy match fails immediately on any other machine. | Clear static index and require automatic rebuilt on installation / boot. | Phase 4 |

---

## 2. Refactoring Log & Resolution Status

* **Status: Resolved** (Phase 0):
  * Removed duplicate root `tools.py` causing python import namespace failures.
  * Patched SMTP connection lifecycle inside `tools/tools.py:send_email` to check credentials prior to socket connections.
  * Modified RAG testing parameters to run correctly with temp directories and code file paths.
  * Added `conftest.py` with headless mocks for platform-specific libraries.

* **Status: Scheduled** (Roadmap Alignment):
  * Database lazy initialization scheduled for Phase 7 (Memory).
  * Stateful browser service refactoring scheduled for Phase 9 (Browser/Computer-Use).
  * Context injection and voice pipeline integration scheduled for Phase 8 (Voice).
