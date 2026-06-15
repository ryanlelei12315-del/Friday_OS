from playwright.async_api import async_playwright


class BrowserService:

    def __init__(self):

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self):

        if self.browser:
            return

        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            channel="chrome",
            headless=False
        )

        self.context = await self.browser.new_context()

        self.page = await self.context.new_page()

    async def stop(self):

        if self.browser:
            await self.browser.close()

        if self.playwright:
            await self.playwright.stop()
            
        try:

            self.browser = await self.playwright.chromium.launch(
                channel="chrome",
                headless=False
            )

        except Exception:

            self.browser = await self.playwright.chromium.launch(
                channel="msedge",
                headless=False
    )