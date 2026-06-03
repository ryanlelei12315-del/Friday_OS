import asyncio

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    noise_cancellation,
)
from memory._init_ import initialize_memory
from livekit.plugins import google
from prompts import FRIDAY_SYSTEM_PROMPT,WELCOME_MESSAGE,FRIDAY_BEHAVIOR,USER_UNDERSTANDING_LAYER
from tools import (
    get_weather,
    search_web,
    send_email
)

from tools_memory import recall_memory
load_dotenv()


class Assistant(Agent):
    def __init__(self) -> None:
        initialize_memory()
        super().__init__(
            instructions=f"{FRIDAY_SYSTEM_PROMPT}\n"
            f"{USER_UNDERSTANDING_LAYER}\n"
            f"{WELCOME_MESSAGE}\n"
            f"{FRIDAY_BEHAVIOR}",
            llm=google.beta.realtime.RealtimeModel(
            voice="Aoede",
            temperature=0.8,

            generation_config={
                "context_window_compression": True,
            }
        ),
            tools=[
                get_weather,
                search_web,
                send_email,
                recall_memory
            ],

        )
        


async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            video_enabled=True,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()
    await asyncio.sleep(0.5) 
    
     # Wait for the session to initialize
    await session.generate_reply(
        instructions=f"{FRIDAY_SYSTEM_PROMPT}\n"
            f"{USER_UNDERSTANDING_LAYER}\n"
            f"{WELCOME_MESSAGE}\n"
            f"{FRIDAY_BEHAVIOR}",
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
