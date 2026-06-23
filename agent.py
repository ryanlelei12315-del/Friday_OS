# Memory and Local Plugin Imports
import asyncio

from dotenv import load_dotenv
from livekit import agents

# FIXED: Correct class name mapping for room input properties
from livekit.agents import Agent, AgentSession, JobContext, room_io
from livekit.plugins import google, noise_cancellation

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
from tools.tools_browser import google_search, open_website, read_website
from tools.tools_files import (
    create_file,
    delete_file,
    find_file,
    list_files,
    move_file,
    read_file,
)
from tools.tools_memory import recall_memory

load_dotenv()


class FridayAgent(Agent):
    def __init__(self) -> None:
        # Run your ChromaDB vector memory layer setup
        initialize_memory()

        super().__init__(
            # Main Voice/Vision Core Instructions
            instructions=f"{FRIDAY_SYSTEM_PROMPT}\n\n{USER_UNDERSTANDING_LAYER}\n\n{FRIDAY_BEHAVIOR}",
            # FIXED: Flattened options and removed the crashing generation_config block
            llm=google.beta.realtime.RealtimeModel(voice="Aoede", temperature=0.7),
            # Complete Integrated Automated Tool Registry
            tools=[
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
            ],
        )


async def entrypoint(ctx: JobContext, context_tracker=None):
    print("[Agent] Initializing LiveKit room connection...")

    if context_tracker:
        print(
            f"Current App Window Title: {context_tracker.current_context['active_window_title']}"
        )

    # 2. This is how your agent dynamically grabs the active screen context on demand:
    def get_live_system_prompt():
        if context_tracker:
            ctx_data = context_tracker.current_context
            return (
                "You are FridayOS, an ambient operating system intelligence.\n"
                f"User's Active Window: {ctx_data['active_window_title']}\n"
                f"Process Name: {ctx_data['active_process_name']}\n"
                f"Clipboard Content: '{ctx_data['clipboard_text']}'\n"
                "Use this data implicitly to assist the user."
            )
        return "You are FridayOS, a helpful voice assistant."

    session = AgentSession()

    # FIXED: Re-mapped to standard production RoomOptions signatures
    await session.start(
        room=ctx.room,
        agent=FridayAgent(),
        room_options=room_io.RoomOptions(
            video_input=room_io.VideoInputOptions(),  # Turns on web camera tracking channel
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC()  # Switches to BVC premium filter
            ),
        ),
    )

    await ctx.connect()
    await asyncio.sleep(0.5)

    # FIXED: Replaced massive prompt concatenation with just the clean phonetic greeting string
    await session.generate_reply(instructions=WELCOME_MESSAGE)


if __name__ == "__main__":
    # FIXED: Correct runner syntax for standalone entrypoint function loops
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
