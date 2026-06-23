async def start_livekit_pipeline(context_tracker):
    """Connects to LiveKit and injects the live OS state into Gemini."""

    # Dynamically compile session parameters with live OS data
    def build_system_instructions():
        ctx = context_tracker.current_context
        base_prompt = (
            "You are FridayOS, an ambient operating system intelligence.\n"
            "You have direct access to the user's desktop environment.\n"
            "CURRENT LIVE RUNTIME CONTEXT:\n"
            f"- Active App Window: {ctx['active_window_title']}\n"
            f"- Process Name: {ctx['active_process_name']}\n"
            f"- Last Copied Clipboard Text: '{ctx['clipboard_text']}'\n\n"
            "Use this context implicitly to answer queries seamlessly."
        )
        return base_prompt

    print("[Pipeline] Connecting to LiveKit Room...")

    # Visual example of how to attach this to your Google Realtime loop:
    #
    # room = rtc.Room()
    # await room.connect(URL, TOKEN)
    #
    # realtime_agent = RealtimeModel(
    #     model="gemini-2.0-flash-exp", # or your specified Gemini Realtime model
    #     system_instruction=build_system_instructions()
    # )

    # We will update these instructions periodically inside your token refresh loop.
    print("[Pipeline] Live context sync engine loaded.")
