"""
DEPRECATED: This file is no longer imported by main.py.

All functionality has been consolidated into Friday_OS/Backend/main.py,
which is the canonical entrypoint for the FridayOS LiveKit agent.

This file is retained for reference only. Do not use as the primary
entrypoint. See main.py for the active implementation.
"""

import json
import sys

from core.friday_rag import ingest_local_document
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    room_io,
)
from livekit.plugins import google, noise_cancellation

# Memory
from memory import initialize_memory

# Prompts
from prompts import (
    FRIDAY_BEHAVIOR,
    FRIDAY_SYSTEM_PROMPT,
    USER_UNDERSTANDING_LAYER,
    WELCOME_MESSAGE,
)

#
# Home Assistant Tools
from tools.home_assistant_tools import (
    get_device_state,
    toggle_device,
    turn_off_device,
    turn_on_device,
)

# General Tools
from tools.tools import (
    get_weather,
    search_web,
    send_email,
    structural_automation_worker,
)

# Application Tools
from tools.tools_apps import (
    close_application,
    is_app_running,
    list_running_apps,
    open_application,
    refresh_app_index,
)

# Browser Tools
from tools.tools_browser import (
    google_search,
    open_website,
    read_website,
)

# File Tools
from tools.tools_files import (
    create_file,
    delete_file,
    find_file,
    list_files,
    move_file,
    read_file,
)

# Memory Tools
from tools.tools_memory import recall_memory

ACTIVE_TRACKER = None
load_dotenv()
server = agents.AgentServer()

# ==========================================================
# MODEL SELECTION
# ==========================================================


def create_model():
    """
    Use text model for console mode.
    Use Gemini Realtime everywhere else.
    """

    if "console" in sys.argv:
        print("[FridayOS] Console mode detected.")
        print("[FridayOS] Using Gemini text model.")

        return google.LLM(model="gemini-2.5-flash")

    print("[FridayOS] Voice mode detected.")
    print("[FridayOS] Using Gemini Realtime.")

    return google.beta.realtime.RealtimeModel(
        voice="Aoede",
        temperature=0.7,
    )


# ==========================================================
# TOOL REGISTRY
# ==========================================================

TOOLS = [
    get_weather,
    search_web,
    send_email,
    recall_memory,
    structural_automation_worker,
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
# AGENT
# ==========================================================


class FridayAgent(Agent):
    def __init__(self):
        initialize_memory()

        instructions = (
            f"{FRIDAY_SYSTEM_PROMPT}\n\n{USER_UNDERSTANDING_LAYER}\n\n{FRIDAY_BEHAVIOR}"
        )

        super().__init__(
            instructions=instructions,
            llm=create_model(),
            tools=TOOLS,
        )


# ==========================================================
# ENTRYPOINT
# ==========================================================


@server.rtc_session()
async def entrypoint(
    ctx: JobContext,
    context_tracker=None,
):
    print("[Agent] Initializing...")

    #
    # Connect first
    #
    await ctx.connect()
    print("[Agent] Connected to room.")

    #
    # Dynamic desktop context
    #
    desktop_context = "You are FridayOS."

    if context_tracker:
        try:
            current = context_tracker.current_context

            print(f"[Agent] Active Window: {current['active_window_title']}")

            desktop_context = (
                "You are FridayOS, an ambient operating "
                "system intelligence.\n"
                f"Active Window: "
                f"{current['active_window_title']}\n"
                f"Process Name: "
                f"{current['active_process_name']}\n"
                f"Clipboard Content: "
                f"{current['clipboard_text']}"
            )

        except Exception as e:
            print(f"[Context Error] {e}")

    @ctx.llm.ai_callable(
        description="Indexes a local file, PDF, or code script into long term memory storage blocks for RAG query recall."
    )
    def learn_local_document(file_path: str):
        print(
            f"[RAG Engine] Commencing ingestion procedure on targeted asset: {file_path}"
        )
        return ingest_local_document(file_path)

    @ctx.llm.ai_callable(
        description="Queries the long term desktop vector knowledge index database to search for specific project facts or information."
    )
    def query_long_term_memory(question: str):
        print(f"[RAG Engine] Performing semantic lookups for question: '{question}'")

    #
    # Create session
    #
    session = AgentSession()

    #
    # CONSOLE MODE
    #
    if "console" in sys.argv:
        print("[Agent] Starting text session...")

        await session.start(
            room=ctx.room,
            agent=FridayAgent(),
        )

        # Safely determine if we are running in an un-emulated mock/console context
        # This breaks the unittest.mock parsing exception chain
        is_mock_participant = hasattr(
            ctx.room.local_participant, "_mock_return_value"
        ) or "mock" in str(type(ctx.room.local_participant))
        # This acts as the direct solution LiveKit is requesting in the error trace log.
        session.output.set_audio_enabled(False)
        print(
            "[Safety Override] Audio generation engine disabled to prevent console exceptions."
        )

        if is_mock_participant:
            print(
                "[Safety Override] LiveKit Mock testing container detected. Bypassing voice stream hooks."
            )
        else:
            # Only execute real media channel tuning if running physical network traffic
            try:
                if (
                    hasattr(ctx.room.local_participant, "is_publisher")
                    and not ctx.room.local_participant.is_publisher
                ):
                    print(
                        "[Safety Override] No speaker/TTS engine available. Switching off active audio channels..."
                    )
                    ctx.room.local_participant.set_metadata(
                        json.dumps({"audio_enabled": False})
                    )
            except Exception as e:
                print(f"[Audio Safety Non-Fatal Error] {e}")

        print("[Agent] Audio output disabled.")
        print("[Agent] Ready.")

        # Optional greeting in console
        try:
            await session.generate_reply(
                instructions=(f"{desktop_context}\n\n{WELCOME_MESSAGE}")
            )
        except Exception as e:
            print(f"[Greeting Error] {e}")

        return

    #
    # VOICE MODE
    #
    print("[Agent] Starting voice session...")

    await session.start(
        room=ctx.room,
        agent=FridayAgent(),
        room_options=room_io.RoomOptions(
            video_input=room_io.VideoInputOptions(),
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC()
            ),
        ),
    )

    try:
        await session.generate_reply(
            instructions=(f"{desktop_context}\n\n{WELCOME_MESSAGE}")
        )
    except Exception as e:
        print(f"[Greeting Error] {e}")

    print("[Agent] Ready.")


# ==========================================================
# STANDALONE EXECUTION
# ==========================================================

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
