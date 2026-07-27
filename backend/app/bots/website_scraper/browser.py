import asyncio
from playwright.async_api import async_playwright, Browser, Page
import logging

logger = logging.getLogger(__name__)

class BrowserManager:
    def __init__(self, headless: bool = True, slow_mo: int = 0, timeout: int = 30000):
        self.headless = headless
        self.slow_mo = slow_mo
        self.timeout = timeout
        self.browser: Browser | None = None
        self.playwright = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def new_page(self) -> Page:
        if not self.browser:
            raise RuntimeError("Browser not initialized")
        context = await self.browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(self.timeout)
        return page
