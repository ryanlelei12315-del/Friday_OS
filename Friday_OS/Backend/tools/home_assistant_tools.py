from livekit.agents import RunContext, function_tool

from automation.home_assistant import (
    HomeAssistantClient,
)

ha = HomeAssistantClient()


@function_tool()
async def turn_on_device(
    context: RunContext,
    entity_id: str,
) -> str:
    """
    Turn on a Home Assistant entity.
    Example:
    light.office
    switch.server_rack
    """

    domain = entity_id.split(".")[0]

    return await ha.call_service(
        domain=domain,
        service="turn_on",
        entity_id=entity_id,
    )


@function_tool()
async def turn_off_device(
    context: RunContext,
    entity_id: str,
) -> str:
    """
    Turn off a Home Assistant entity.
    """

    domain = entity_id.split(".")[0]

    return await ha.call_service(
        domain=domain,
        service="turn_off",
        entity_id=entity_id,
    )


@function_tool()
async def toggle_device(
    context: RunContext,
    entity_id: str,
) -> str:
    """
    Toggle a Home Assistant entity.
    """

    domain = entity_id.split(".")[0]

    return await ha.call_service(
        domain=domain,
        service="toggle",
        entity_id=entity_id,
    )


@function_tool()
async def get_device_state(
    context: RunContext,
    entity_id: str,
) -> str:
    """
    Retrieve current device state.
    """

    return await ha.get_state(entity_id=entity_id)
