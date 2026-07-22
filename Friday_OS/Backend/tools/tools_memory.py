from livekit.agents import RunContext, function_tool

from memory.long_term import search_memory


@function_tool()
async def recall_memory(context: RunContext, query: str) -> str:

    results = search_memory(query)

    return str(results)


@function_tool()
async def extract_memory(
    transcript: str,
) -> str:

    results = search_memory(transcript)

    return str(results)
