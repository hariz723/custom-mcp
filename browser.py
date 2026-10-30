import asyncio
import logging

from bs4 import BeautifulSoup
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)  # type: ignore

from config import DEFAULT_TIMEOUT_MS, HEADLESS, VIEWPORT_HEIGHT, VIEWPORT_WIDTH

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages the lifecycle of Playwright, Browser, Context, and Page."""

    def __init__(self):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._lock = asyncio.Lock()

    async def get_page(self) -> Page:
        """Returns the active page, creating browser and context if needed."""
        async with self._lock:
            if self._page is not None and not self._page.is_closed():
                return self._page

            if self._playwright is None:
                logger.info("Starting Playwright driver...")
                self._playwright = await async_playwright().start()

            if self._browser is None or not self._browser.is_connected():
                logger.info("Launching Chromium browser (headless=%s)...", HEADLESS)
                self._browser = await self._playwright.chromium.launch(
                    headless=HEADLESS,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--no-first-run",
                        "--no-zygote",
                    ],
                )

            if self._context is None:
                logger.info("Creating browser context...")
                self._context = await self._browser.new_context(
                    viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                    ),
                    ignore_https_errors=True,
                )
                self._context.set_default_timeout(DEFAULT_TIMEOUT_MS)

            logger.info("Creating new page...")
            self._page = await self._context.new_page()
            return self._page

    async def reset(self) -> None:
        """Resets the current page and context, preserving the browser."""
        async with self._lock:
            if self._page and not self._page.is_closed():
                await self._page.close()
                self._page = None

            if self._context:
                await self._context.close()
                self._context = None
            logger.info("Browser context reset.")

    async def close(self) -> None:
        """Closes all browser resources and stops Playwright."""
        async with self._lock:
            if self._page and not self._page.is_closed():
                await self._page.close()
                self._page = None

            if self._context:
                await self._context.close()
                self._context = None

            if self._browser and self._browser.is_connected():
                await self._browser.close()
                self._browser = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            logger.info("Browser shut down cleanly.")


# Global singleton instance
browser_manager = BrowserManager()


def clean_html_content(raw_html: str, max_length: int = 25000) -> str:
    """Cleans HTML to optimize token usage for LLMs."""
    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove script, style, meta, link, svg, and noscript tags
    for tag in soup(["script", "style", "meta", "link", "svg", "noscript", "iframe"]):
        tag.decompose()

    # Get string representation
    cleaned = str(soup)

    if len(cleaned) > max_length:
        return cleaned[:max_length] + f"\n... [Truncated: {len(cleaned) - max_length} additional characters]"
    return cleaned
