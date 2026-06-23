import asyncio
import os
import sys

from livekit.agents import AgentServer, JobContext, cli

from agent import entrypoint
from core.automation import FridayAutomationManager
from core.tracker import AmbientContextTracker
from pipeline.livekit_client import start_livekit_pipeline

project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

server = AgentServer()


@server.rtc_session()
async def rtc_session_entrypoint(ctx: JobContext):
    """
    This wrapper function fires every time a participant joins the room.
    It injects our running ambient background tracker state directly into your agent.
    """
    print(
        "[LiveKit Server] New room session captured! Injecting OS environment context..."
    )

    # Hand over execution to your original agent code, passing the active tracker along
    await entrypoint(ctx, context_tracker=context_tracker)


def prewarm_subsystems(server_instance):
    """
    Fires right before the network layer binds. Wakes up the background OS sensors.
    """
    global context_tracker, automation
    print("====== FRIDAY OS MASTER BOOT SEQUENCE ======")

    # 1. Start the window and clipboard desktop listener
    context_tracker = AmbientContextTracker()
    context_tracker.start()
    print("[Boot] Ambient context tracking active.")

    # 2. Start the filesystem Downloads watcher
    automation = FridayAutomationManager()
    automation.start()
    print("[Boot] Background file automation active.")


if __name__ == "__main__":
    if sys.platform != "win32":
        print("FridayOS core modules require a Windows operating system.")
        sys.exit(1)

    # Attach our startup hook to the AgentServer configuration instance
    server.setup_fnc = prewarm_subsystems

    print(
        "[Boot] Handoff complete. Passing application thread to LiveKit CLI wrapper..."
    )
    try:
        # This native LiveKit function handles the incoming arguments ('dev', 'console', 'start') safely
        cli.run_app(server)
    finally:
        # Graceful cleanup structure to kill background threads when you close the server
        print("\n[Shutdown] Shutting down FridayOS tracking subsystems...")
        if automation:
            automation.stop()
        if context_tracker:
            context_tracker.stop()
        print("[Shutdown] Systems safely offline.")


async def run_friday_os():
    print("====== FRIDAY OS MASTER BOOT SEQUENCE ======")

    # 1. Start the ambient desktop window & clipboard monitor
    tracker = AmbientContextTracker()
    tracker.start()
    print("[Boot] Ambient context tracking active.")

    # 2. Start the automated Downloads folder watcher
    automation = FridayAutomationManager()
    automation.start()
    print("[Boot] Background file automation active.")

    # 3. Fire up the LiveKit Agent Server and feed it our system tracker
    # We wrap your original entrypoint inside a lambda function so it gets the tracker parameter cleanly
    server = AgentServer(
        agent_entrypoint=lambda ctx: entrypoint(ctx, context_tracker=tracker)
    )

    try:
        print("[Boot] Handoff complete. Handing over to LiveKit room listeners...")
        await server.run()  # This keeps your voice loop running indefinitely
    except KeyboardInterrupt:
        print("\n[Shutdown] Shutting down FridayOS subsystems...")
    finally:
        # Prevent memory leaks by shutting background loops down cleanly
        automation.stop()
        tracker.stop()
        print("[Shutdown] Systems safely offline.")


if __name__ == "__main__":
    if sys.platform != "win32":
        print("FridayOS requires a Windows environment.")
        sys.exit(1)

    asyncio.run(run_friday_os())


async def main():
    print("[FridayOS] Initializing subsystems...")

    # 1. Start Context Tracking
    tracker = AmbientContextTracker()
    tracker.start()
    print("[FridayOS] Ambient monitoring active.")

    # 2. Run the Voice/Vision Pipeline alongside MCP triggers
    try:
        print("[FridayOS] Connecting to LiveKit room...")
        await start_livekit_pipeline(context_provider=tracker)
    except KeyboardInterrupt:
        print("[FridayOS] Shutting down...")
    finally:
        tracker.stop()


if __name__ == "__main__":
    if sys.platform != "win32":
        print("FridayOS core modules require Windows.")
        sys.exit(1)
    asyncio.run(main())


async def run_os_agent():
    print("====== FRIDAY OS BOOT SEQUENCE ======")

    # 1. Initialize Ambient System Information Tracing
    tracker = AmbientContextTracker()
    tracker.start()
    print("[Boot] Ambient context tracking running.")

    # 2. Launch Local Automated System Watchers
    automation = FridayAutomationManager()
    automation.start()
    print("[Boot] Background event handlers linked.")

    # 3. Connect to the LiveKit Audio / Vision Channel
    try:
        await start_livekit_pipeline(context_tracker=tracker)

        # Keep the background process alive infinitely
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n[Shutdown] Halting FridayOS engine components...")
    finally:
        automation.stop()
        tracker.stop()
        print("[Shutdown] Clean exit finalized.")


if __name__ == "__main__":
    asyncio.run(run_os_agent())


async def your_existing_main_function():
    print("[FridayOS] Initializing OS layers...")

    # Start the ambient tracking background thread
    context_tracker = AmbientContextTracker()
    context_tracker.start()

    # Start the filesystem automation layer
    automation = FridayAutomationManager()
    automation.start()

    # --- DYNAMIC INJECTION CONFIG ---
    # Whenever your existing Gemini loop sets up or updates its prompt instructions,
    # you can now pull the fresh live desktop state like this:
    def get_live_system_prompt():
        ctx = context_tracker.current_context
        return (
            "You are FridayOS.\n"
            f"User Active App: {ctx['active_window_title']}\n"
            f"Process Name: {ctx['active_process_name']}\n"
            f"Clipboard Content: '{ctx['clipboard_text']}'"
        )

    # --------------------------------

    # YOUR ORIGINAL LIVEKIT ROOM CONNECTION AND LOGIC CONTINUES BELOW...
    # (e.g., await room.connect(...))

    try:
        # Keep your existing loop running here
        pass
    finally:
        # Clean up background services when exiting
        automation.stop()
        context_tracker.stop()
