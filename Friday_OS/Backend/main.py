"""
FridayOS Main Entrypoint
LiveKit + Ambient Context + Automation Layer
"""

import json
import os
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    cli,
    function_tool,
    room_io,
)
from livekit.plugins import noise_cancellation, openai

from core.automation import FridayAutomationManager
from core.friday_rag import ingest_local_document, query_desktop_knowledge
from core.tracker import AmbientContextTracker
from memory import initialize_memory

from prompts import (
    FRIDAY_BEHAVIOR,
    FRIDAY_SYSTEM_PROMPT,
    USER_UNDERSTANDING_LAYER,
    WELCOME_MESSAGE,
)

from tools.home_assistant_tools import (
    get_device_state,
    toggle_device,
    turn_off_device,
    turn_on_device,
)

from tools.tools import (
    get_weather,
    search_web,
    send_email,
    structural_automation_worker,
)

from tools.tools_apps import (
    close_application,
    is_app_running,
    list_running_apps,
    open_application,
    refresh_app_index,
)

from tools.tools_browser import (
    google_search,
    open_website,
    read_website,
)

from tools.tools_files import (
    create_file,
    delete_file,
    find_file,
    list_files,
    move_file,
    read_file,
)

from tools.tools_memory import recall_memory


# ==========================================================
# PATH AND ENVIRONMENT
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FRIDAY_VOICE_MODEL = os.getenv("FRIDAY_VOICE_MODEL", "gpt-live-1")
FRIDAY_BACKEND_MODEL = os.getenv("FRIDAY_BACKEND_MODEL", "gpt-5.6-luna")

if not OPENAI_API_KEY:
    print("[Warning] OPENAI_API_KEY not found in environment variables.")


# ==========================================================
# MODEL ORCHESTRATION
# ==========================================================

def create_model():
    """
    Build the real-time ChatGPT orchestration loop.

    Voice mode:
      GPT-Live handles low-latency speech and delegates reasoning/tool work
      to a separate OpenAI Responses model.

    Console mode:
      Use the same backend frontier model through the Responses API.
    """
    if "console" in sys.argv:
        print("[FridayOS] Console mode detected.")
        print(f"[FridayOS] Using OpenAI Responses model: {FRIDAY_BACKEND_MODEL}.")
        return openai.responses.LLM(model=FRIDAY_BACKEND_MODEL)

    print("[FridayOS] Voice mode detected.")
    print(f"[FridayOS] Using GPT-Live voice model: {FRIDAY_VOICE_MODEL}.")
    print(f"[FridayOS] Delegating reasoning to: {FRIDAY_BACKEND_MODEL}.")

    return openai.realtime.GPTLiveModel(
        model=FRIDAY_VOICE_MODEL,
        voice="alloy",
        delegation="responses",
        responses_options={
            "model": FRIDAY_BACKEND_MODEL,
            "instructions": (
                "You are the reasoning and execution layer behind FRIDAY. "
                "Handle delegated requests with precision. Use the registered "
                "function tools whenever they are required to obtain current "
                "information or perform an action. Prefer direct tool execution "
                "over explaining how the user could do it manually. After tool "
                "execution, return a concise result suitable for FRIDAY to speak aloud."
            ),
            "parallel_tool_calls": True,
            "reasoning": {"effort": "medium"},
            "text": {"verbosity": "low"},
        },
    )


# ==========================================================
# TOOL REGISTRY
# ==========================================================
#
# The four orchestration-critical tools are intentionally kept
# together at the top of the runner array:
#
#   search_web
#   send_email
#   structural_automation_worker
#   recall_memory
#
# Existing desktop, browser, file, and home-assistant tools remain
# registered so the orchestration layer does not regress existing
# FridayOS capabilities.
#

ORCHESTRATION_TOOLS = [
    search_web,
    send_email,
    structural_automation_worker,
    recall_memory,
]

TOOLS = [
    *ORCHESTRATION_TOOLS,
    get_weather,
    list_files,
    find_file,
    create_file,
    read_file,
    move_file,
    delete_file,
    refresh_app_index,
    list_running_apps,
    open_application,
    close_application,
    is_app_running,
    open_website,
    google_search,
    read_website,
    turn_on_device,
    turn_off_device,
    toggle_device,
    get_device_state,
]


# ==========================================================
# RAG TOOLS
# ==========================================================

@function_tool(
    description=(
        "Indexes a local file, PDF, or code script into long term memory "
        "storage blocks for RAG query recall."
    )
)
def learn_local_document(file_path: str):
    print(
        f"[RAG Engine] Commencing ingestion procedure on targeted asset: {file_path}"
    )
    return ingest_local_document(file_path)


@function_tool(
    description=(
        "Queries the long term desktop vector knowledge index database "
        "to search for specific project facts or information."
    )
)
def query_long_term_memory(question: str):
    print(
        f"[RAG Engine] Performing semantic lookups for question: '{question}'"
    )
    return query_desktop_knowledge(question)


TOOLS += [
    learn_local_document,
    query_long_term_memory,
]


# ==========================================================
# AGENT
# ==========================================================

class FridayAgent(Agent):
    def __init__(self) -> None:
        initialize_memory()

        voice_instructions = (
            f"{FRIDAY_SYSTEM_PROMPT}\n\n"
            f"{USER_UNDERSTANDING_LAYER}\n\n"
            f"{FRIDAY_BEHAVIOR}\n\n"
            "Delegation rule: answer simple conversational requests directly. "
            "For requests requiring web research, memory lookup, email, desktop "
            "automation, file operations, application control, or other external "
            "actions, delegate the work to the reasoning layer and keep the user "
            "informed briefly while it executes."
        )

        super().__init__(
            instructions=voice_instructions,
            llm=create_model(),
            tools=TOOLS,
        )


# ==========================================================
# LIVEKIT SERVER
# ==========================================================

server = AgentServer()


# ==========================================================
# SUBSYSTEM BOOT
# ==========================================================

def boot_subsystems(proc=None):
    """
    Called once by LiveKit when a worker process starts.
    """
    global context_tracker
    global automation_manager

    print("====================================")
    print("         FRIDAY OS BOOT")
    print("====================================")

    if context_tracker is None:
        context_tracker = AmbientContextTracker()
        context_tracker.start()
        print("[Boot] Ambient context tracker started.")

    if automation_manager is None:
        automation_manager = FridayAutomationManager()
        automation_manager.start()
        print("[Boot] Automation manager started.")

    print("[Boot] All subsystems online and mapped to Agent module state.")


# ==========================================================
# SUBSYSTEM SHUTDOWN
# ==========================================================

def shutdown_subsystems():
    """
    Gracefully shuts down background services.
    """
    global context_tracker
    global automation_manager

    print("\n====================================")
    print("       FRIDAY OS SHUTDOWN")
    print("====================================")

    try:
        if automation_manager:
            automation_manager.stop()
            automation_manager = None
            print("[Shutdown] Automation manager stopped.")

        if context_tracker:
            context_tracker.stop()
            context_tracker = None
            print("[Shutdown] Context tracker stopped.")

    except Exception as e:
        print(f"[Shutdown Error] {e}")

    print("[Shutdown] FridayOS safely offline.")


# ==========================================================
# GLOBAL REFERENCES
# ==========================================================

context_tracker: AmbientContextTracker | None = None
automation_manager: FridayAutomationManager | None = None


# ==========================================================
# RTC SESSION
# ==========================================================

@server.rtc_session()
async def entrypoint(
    ctx: JobContext,
    context_tracker=None,
):
    print("[Agent] Initializing...")

    await ctx.connect()
    print("[Agent] Connected to room.")

    desktop_context = "You are FridayOS."

    if context_tracker:
        try:
            current = context_tracker.current_context

            print(f"[Agent] Active Window: {current['active_window_title']}")

            desktop_context = (
                "You are FridayOS, an ambient operating system intelligence.\n"
                f"Active Window: {current['active_window_title']}\n"
                f"Process Name: {current['active_process_name']}\n"
                f"Clipboard Content: {current['clipboard_text']}"
            )

        except Exception as e:
            print(f"[Context Error] {e}")

    session = AgentSession()

    # ======================================================
    # CONSOLE MODE
    # ======================================================

    if "console" in sys.argv:
        print("[Agent] Starting text session...")

        await session.start(
            room=ctx.room,
            agent=FridayAgent(),
        )

        is_mock_participant = hasattr(
            ctx.room.local_participant, "_mock_return_value"
        ) or "mock" in str(type(ctx.room.local_participant))

        session.output.set_audio_enabled(False)
        print(
            "[Safety Override] Audio generation engine disabled to prevent console exceptions."
        )

        if is_mock_participant:
            print(
                "[Safety Override] LiveKit Mock testing container detected. "
                "Bypassing voice stream hooks."
            )
        else:
            try:
                if (
                    hasattr(ctx.room.local_participant, "is_publisher")
                    and not ctx.room.local_participant.is_publisher
                ):
                    print(
                        "[Safety Override] No speaker/TTS engine available. "
                        "Switching off active audio channels..."
                    )
                    ctx.room.local_participant.set_metadata(
                        json.dumps({"audio_enabled": False})
                    )
            except Exception as e:
                print(f"[Audio Safety Non-Fatal Error] {e}")

        print("[Agent] Audio output disabled.")
        print("[Agent] Ready.")

        try:
            await session.generate_reply(
                instructions=f"{desktop_context}\n\n{WELCOME_MESSAGE}"
            )
        except Exception as e:
            print(f"[Greeting Error] {e}")

        return

    # ======================================================
    # VOICE MODE
    # ======================================================

    print("[Agent] Starting voice session...")

    await session.start(
        room=ctx.room,
        agent=FridayAgent(),
        room_options=room_io.RoomOptions(
            video_input=room_io.VideoInputOptions(),
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )

    try:
        await session.generate_reply(
            instructions=f"{desktop_context}\n\n{WELCOME_MESSAGE}"
        )
    except Exception as e:
        print(f"[Greeting Error] {e}")

    print("[Agent] Ready.")


# ==========================================================
# SIGNAL HANDLING
# ==========================================================

def handle_exit(signum, frame):
    """
    Handles Ctrl+C and process termination.
    """
    print(f"\n[Signal] Received signal {signum}")
    shutdown_subsystems()
    sys.exit(0)


# ==========================================================
# MAIN
# ==========================================================

def main():
    if sys.platform != "win32":
        print("FridayOS requires Windows.")
        sys.exit(1)

    signal.signal(signal.SIGINT, handle_exit)

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_exit)

    server.setup_fnc = boot_subsystems

    print("[Boot] Handing execution to LiveKit Agent Server...")

    try:
        cli.run_app(server)
    finally:
        shutdown_subsystems()


if __name__ == "__main__":
    main()
