import asyncio
import logging
import traceback
from typing import Tuple, Optional

import httpx

logger = logging.getLogger(__name__)

# Common browser-like headers to avoid 403/bot-detection blocks
# NOTE: Do NOT include Accept-Encoding — let httpx handle decompression
# automatically. Manually setting it bypasses httpx's auto-decompression
# and returns raw gzip binary bytes instead of decoded HTML text.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class Crawler:
    """Fetch a web page using httpx (async HTTP client).

    Replaces the Playwright-based implementation because Playwright's
    asyncio.create_subprocess_exec raises NotImplementedError on Windows
    with Python 3.14 when running inside uvicorn's event loop.

    httpx is a modern async HTTP client that works on all platforms without
    spawning subprocesses.
    """

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        timeout: int = 30000,
        max_retries: int = 3,
    ):
        # timeout is stored in ms for compatibility; httpx uses seconds
        self.timeout_seconds = timeout / 1000
        self.max_retries = max_retries

    async def fetch(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Fetch *url* and return (html_content, final_url) after redirects.

        Returns (None, None) if all attempts fail.
        """
        attempt = 0
        backoff = 1
        last_error: Optional[str] = None

        while attempt < self.max_retries:
            attempt += 1
            logger.info("[Crawler] Attempt %d/%d — fetching: %s", attempt, self.max_retries, url)
            try:
                async with httpx.AsyncClient(
                    headers=_HEADERS,
                    follow_redirects=True,
                    verify=False,          # ignore SSL errors (same as Playwright's ignore_https_errors)
                    timeout=self.timeout_seconds,
                ) as client:
                    logger.info("[Crawler] Sending GET request to %s …", url)
                    response = await client.get(url)
                    final_url = str(response.url)
                    html = response.text
                    logger.info(
                        "[Crawler] Success — status=%d, final_url=%s, html_length=%d",
                        response.status_code,
                        final_url,
                        len(html),
                    )
                    return html, final_url

            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "[Crawler] Attempt %d/%d failed for %s: %s\n%s",
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                    traceback.format_exc(),
                )
                if attempt < self.max_retries:
                    logger.info("[Crawler] Retrying in %ds …", backoff)
                    await asyncio.sleep(backoff)
                    backoff *= 2

        logger.error(
            "[Crawler] All %d attempts failed for %s. Last error: %s",
            self.max_retries,
            url,
            last_error,
        )
        return None, None
