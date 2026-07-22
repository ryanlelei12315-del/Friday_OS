from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from browser.browser_service import BrowserService

browser_service = BrowserService()


@tool
async def start_browser(config: RunnableConfig) -> str:
    """Starts the background browser service instance."""
    await browser_service.start()
    return "Browser started."


@tool
async def navigate_to(url: str, config: RunnableConfig) -> str:
    """Navigates the browser to a specific target URL."""
    await browser_service.start()
    await browser_service.page.goto(url)
    return f"Opened {url}"


@tool
async def google_search(query: str, config: RunnableConfig) -> str:
    """Executes a Google search query and extracts the text content."""
    await browser_service.start()
    search_url = f"https://www.google.com/search?q={query}"
    await browser_service.page.goto(search_url)
    text = await browser_service.page.text_content("body")
    return text[:8000]


@tool
async def read_current_page(config: RunnableConfig) -> str:
    """Reads the text data out of the active browser screen layer."""
    await browser_service.start()
    text = await browser_service.page.text_content("body")
    return text[:10000]


@tool
async def open_new_tab(url: str, config: RunnableConfig) -> str:
    """Spawns an isolated browser window tab and visits a website URL."""
    await browser_service.start()
    page = await browser_service.context.new_page()
    await page.goto(url)
    return f"Opened tab: {url}"
