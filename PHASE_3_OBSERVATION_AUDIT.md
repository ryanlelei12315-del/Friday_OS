# Phase 3 — Windows Observation & State Audit

This document details the deep audit of all 9 conformed Windows capabilities established in Phase 2. It assesses their current observation/mutation boundaries, return payloads, and identifies crucial gaps needed to implement a robust, verified computer control system.

---

## Existing Capability Audit Matrix

| Capability Name | Tool Class | What it Observes | What it Changes | Returned Payload | Gaps / Genuinely Verified? | Action Needed in Phase 3 |
|:---|:---|:---|:---|:---|:---|:---|
| `system.get_info` | `SystemGetInfoTool` | Static host OS platform, CPU count, memory size. | None (Read-only) | Static metadata dict. | No dynamic state tracked. | Preserve as-is. |
| `system.get_cpu_usage` | `SystemGetCpuUsageTool` | Active CPU usage percentage. | None (Read-only) | Numeric value (percent). | High polling latency. | Preserve as-is. |
| `system.get_memory_usage` | `SystemGetMemoryUsageTool` | Active RAM allocation size & availability. | None (Read-only) | Detailed memory metrics. | No historical metrics tracking. | Preserve as-is. |
| `process.list` | `ProcessListTool` | Active process names, PIDs, and memory footprint. | None (Read-only) | Formatted process list (limited to 150). | High context window bloat if unfiltered. | Enforce task-specific process list filtering. |
| `application.list` | `ApplicationListTool` | Hardcoded mock dictionary of safe application descriptions. | None (Read-only) | Fixed text dictionary list. | Extremely static. Prone to reporting wrong status. | **REPLACE**: Build dynamic Windows Application Discovery / Registry. |
| `application.launch` | `ApplicationLaunchTool` | Validates target app name against allowlist. | Spawns a non-shell subprocess. | Status, observation, process PID. | Basic verification by scanning `process.list` with a sleep delay. | **REFACTOR**: Integrate with state snapshots and explicit verification result states. |
| `filesystem.list` | `FilesystemListTool` | Lists items in sandboxed workspace directory. | None (Read-only) | Formatted string of directories. | Traversal checks are correct, but lacks recursive checks. | Preserve. Add workspace context compression. |
| `filesystem.read` | `FilesystemReadTool` | Reads first 8000 bytes of sandbox file. | None (Read-only) | Raw string of file content. | Hard cap on character read buffer. | Preserve. |
| `terminal.execute` | `TerminalExecuteTool` | Runs secure PowerShell command inside sandbox. | System state changes (sandbox directory files). | Stdout, stderr, exit code, execution time. | High risk if command output is unchecked. No pre/post state capture. | **REFACTOR**: Enforce pre/post state snapshots and explicit verification checks. |

---

## Gaps Identified for State Awareness

1. **Passive Window Awareness**: The current system possesses absolutely no knowledge of active UI window titles, visible app panels, or focus states during tool runs.
2. **Missing State Transitions**: Actions (like `application.launch`) are "fire-and-forget" with primitive verifications. There is no formal way of comparing **State A (Before Action)** to **State B (After Action)** to confirm transition success.
3. **Static Application Registry**: Friday assumes VS Code is simply launchable via `code` or notepad is launchable via `notepad.exe`. It cannot inspect actual registry installation paths or discover new apps.
4. **Context Bloat Risk**: Direct process lists or directory lists return raw, bulky text blocks. We must build a context compression engine to deliver only task-specific context back to the LLM.
