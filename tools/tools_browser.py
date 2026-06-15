from urllib.parse import quote_plus

from livekit.agents import RunContext, function_tool
from playwright.async_api import async_playwright


@function_tool()
async def open_website(context: RunContext, url: str) -> str:
    """
    Open a website in browser.
    """

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)

            page = await browser.new_page()

            await page.goto(url)

            return f"Opened {url}"

    except Exception as e:
        return str(e)


@function_tool()
async def google_search(context: RunContext, query: str) -> str:
    """
    Search Google.
    """

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            page = await browser.new_page()

            await page.goto(f"https://www.google.com/search?q={quote_plus(query)}")

            content = await page.content()

            await browser.close()

            return content[:5000]

    except Exception as e:
        return str(e)


@function_tool()
async def read_website(context: RunContext, url: str) -> str:
    """
    Read page content.
    """

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            page = await browser.new_page()

            await page.goto(url)

            text = await page.text_content("body")

            await browser.close()

            return text[:10000]

    except Exception as e:
        return str(e)
