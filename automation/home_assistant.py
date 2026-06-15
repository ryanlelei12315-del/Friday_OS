import logging
import os

import aiohttp


class HomeAssistantClient:
    def __init__(self):
        self.base_url = os.getenv("HOME_ASSISTANT_URL")
        self.token = os.getenv("HOME_ASSISTANT_TOKEN")

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
    ) -> str:
        try:
            url = f"{self.base_url}/api/services/{domain}/{service}"

            payload = {
                "entity_id": entity_id,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=15,
                ) as response:
                    if response.status in (200, 201):
                        return (
                            f"Successfully executed {domain}.{service} on {entity_id}"
                        )

                    text = await response.text()

                    return f"Home Assistant returned {response.status}: {text}"

        except Exception as e:
            logging.exception("Home Assistant service call failed")
            return str(e)

    async def get_state(
        self,
        entity_id: str,
    ) -> str:
        try:
            url = f"{self.base_url}/api/states/{entity_id}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=15,
                ) as response:
                    if response.status != 200:
                        return f"Unable to retrieve state for {entity_id}"

                    data = await response.json()

                    return f"{entity_id} is currently {data.get('state')}"

        except Exception as e:
            logging.exception("Home Assistant state lookup failed")
            return str(e)
