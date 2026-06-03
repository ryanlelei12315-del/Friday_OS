from livekit.agents import function_tool
from livekit.agents import RunContext

from memory.long_term import search_memory


@function_tool()
async def recall_memory(
    context: RunContext,
    query: str
) -> str:

    results = search_memory(query)

    return str(results)