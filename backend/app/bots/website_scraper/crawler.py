import asyncio
import logging
import requests
from typing import Dict, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.4 Mobile/15E148 Safari/604.1"
)

_HEADERS = {
    "User-Agent": DESKTOP_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


def classify_crawl_error(exc: Exception | str) -> str:
    err_str = str(exc).lower()
    if any(k in err_str for k in ["err_name_not_resolved", "name or service not known", "gaierror", "nodename nor servname"]):
        return "DNS Failure"
    if any(k in err_str for k in ["timeout", "timed out"]):
        return "Timeout"
    if "404" in err_str:
        return "HTTP 404"
    if "403" in err_str:
        return "HTTP 403"
    if any(k in err_str for k in ["ssl", "certificate_verify_failed", "cert"]):
        return "SSL Error"
    if any(k in err_str for k in ["err_connection_refused", "connecterror", "connection refused", "unreachable"]):
        return "Unreachable"
    return f"Failed ({str(exc)[:30]})"


class Crawler:
    """Multi-stage robust web crawler: Playwright Desktop -> Playwright Mobile -> HTTPX -> Requests (No JS)."""

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        timeout: int = 25000,
        max_retries: int = 3,
    ):
        self.headless = headless
        self.timeout = timeout
        self.max_retries = max_retries

    async def _fetch_playwright(self, url: str, user_agent: str) -> Tuple[Dict[str, str], Optional[str]]:
        from playwright.async_api import async_playwright

        pages: Dict[str, str] = {}
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            context = await browser.new_context(
                user_agent=user_agent,
                ignore_https_errors=True,
            )
            page = await context.new_page()
            page.set_default_timeout(self.timeout)

            logger.info("[Crawler] Playwright fetching %s (UA: %s)", url, "Mobile" if "iPhone" in user_agent else "Desktop")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
            
            if response and response.status >= 400:
                raise Exception(f"HTTP {response.status}")

            final_url = page.url or url
            main_html = await page.content()
            pages[final_url] = main_html

            # Discover internal contact/about pages
            soup = BeautifulSoup(main_html, "lxml")
            sub_urls = set()
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                txt = (a.get_text() or "").lower()
                href_lower = href.lower()
                if any(k in txt or k in href_lower for k in ["contact", "about", "reach-us", "who-we-are", "team"]):
                    if href.startswith("http"):
                        sub_urls.add(href)
                    elif href.startswith("/"):
                        sub_urls.add(urljoin(final_url, href))

            for sub_url in list(sub_urls)[:2]:
                if sub_url not in pages:
                    try:
                        logger.info("[Crawler] Crawling sub-page: %s", sub_url)
                        await page.goto(sub_url, wait_until="domcontentloaded", timeout=12000)
                        pages[page.url or sub_url] = await page.content()
                    except Exception as err:
                        logger.warning("[Crawler] Sub-page crawl skipped %s: %s", sub_url, err)

            await browser.close()
        return pages, final_url

    async def _fetch_httpx(self, url: str) -> Tuple[Dict[str, str], Optional[str]]:
        logger.info("[Crawler] Stage 3: HTTPX GET for %s", url)
        pages: Dict[str, str] = {}
        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,
            verify=False,
            timeout=self.timeout / 1000,
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                raise Exception(f"HTTP {resp.status_code}")
            final_url = str(resp.url)
            main_html = resp.text
            pages[final_url] = main_html

            soup = BeautifulSoup(main_html, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                txt = (a.get_text() or "").lower()
                if "contact" in txt or "contact" in href.lower() or "about" in txt:
                    sub_url = href if href.startswith("http") else urljoin(final_url, href)
                    try:
                        sub_resp = await client.get(sub_url)
                        if sub_resp.status_code < 400:
                            pages[str(sub_resp.url)] = sub_resp.text
                    except Exception:
                        pass
                    break
        return pages, final_url

    def _fetch_requests(self, url: str) -> Tuple[Dict[str, str], Optional[str]]:
        logger.info("[Crawler] Stage 4: Requests (No JS) GET for %s", url)
        pages: Dict[str, str] = {}
        resp = requests.get(url, headers=_HEADERS, timeout=15, verify=False)
        if resp.status_code >= 400:
            raise Exception(f"HTTP {resp.status_code}")
        final_url = str(resp.url)
        pages[final_url] = resp.text
        return pages, final_url

    async def crawl_site(self) -> Tuple[Dict[str, str], Optional[str], Optional[str]]:
        """
        Public entrypoint: returns (pages_dict, primary_final_url, failure_reason_if_any).
        """
        pass

    async def crawl_url(self, url: str) -> Tuple[Dict[str, str], Optional[str], Optional[str]]:
        normalized_url = url.strip()
        if not normalized_url.startswith(("http://", "https://")):
            normalized_url = "https://" + normalized_url

        last_exc: Optional[Exception] = None

        # Stage 1: Playwright Desktop UA
        try:
            pages, primary_url = await self._fetch_playwright(normalized_url, DESKTOP_UA)
            if pages:
                return pages, primary_url, None
        except Exception as exc:
            last_exc = exc
            logger.warning("[Crawler] Stage 1 (Playwright Desktop) failed for %s: %s", normalized_url, exc)

        # Stage 2: Playwright Mobile UA
        try:
            pages, primary_url = await self._fetch_playwright(normalized_url, MOBILE_UA)
            if pages:
                return pages, primary_url, None
        except Exception as exc:
            last_exc = exc
            logger.warning("[Crawler] Stage 2 (Playwright Mobile) failed for %s: %s", normalized_url, exc)

        # Stage 3: HTTPX Async
        try:
            pages, primary_url = await self._fetch_httpx(normalized_url)
            if pages:
                return pages, primary_url, None
        except Exception as exc:
            last_exc = exc
            logger.warning("[Crawler] Stage 3 (HTTPX) failed for %s: %s", normalized_url, exc)

        # Stage 4: Requests Sync (No JS)
        try:
            loop = asyncio.get_event_loop()
            pages, primary_url = await loop.run_in_executor(None, self._fetch_requests, normalized_url)
            if pages:
                return pages, primary_url, None
        except Exception as exc:
            last_exc = exc
            logger.warning("[Crawler] Stage 4 (Requests No-JS) failed for %s: %s", normalized_url, exc)

        reason = classify_crawl_error(last_exc or "Fetch failed")
        logger.error("[Crawler] All 4 crawl stages failed for %s. Classified reason: %s", normalized_url, reason)
        return {}, None, reason
