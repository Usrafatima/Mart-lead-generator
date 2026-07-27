import logging
from typing import List, Set, Dict, Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class HTMLParser:
    """Parse raw HTML and provide common extraction helpers.

    All methods are synchronous because they operate on the already‑fetched HTML
    string. The surrounding workflow (scraper) is asynchronous.
    """

    def __init__(self, html: str, base_url: str):
        self.html = html
        self.base_url = base_url.rstrip('/')
        self.soup = BeautifulSoup(html, "lxml")

    def get_title(self) -> str:
        title_tag = self.soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        logger.debug("Parsed title: %s", title)
        return title

    def get_meta_tags(self) -> Dict[str, str]:
        meta: Dict[str, str] = {}
        for tag in self.soup.find_all("meta"):
            if tag.get("name"):
                meta[tag["name"].lower()] = tag.get("content", "")
            elif tag.get("property"):
                meta[tag["property"].lower()] = tag.get("content", "")
        logger.debug("Found %d meta tags", len(meta))
        return meta

    def _normalize_url(self, href: str) -> str:
        # Convert relative URLs to absolute based on the base URL.
        if not href:
            return ""
        parsed = urlparse(href)
        if parsed.scheme:
            return href
        return urljoin(self.base_url + '/', href)

    def get_internal_links(self) -> List[str]:
        """Return a list of unique absolute URLs that belong to the same domain.
        """
        domain = urlparse(self.base_url).netloc
        links: Set[str] = set()
        for a in self.soup.find_all("a", href=True):
            href = a["href"].strip()
            abs_url = self._normalize_url(href)
            if not abs_url:
                continue
            if urlparse(abs_url).netloc == domain:
                links.add(abs_url.rstrip('/'))
        logger.debug("Extracted %d internal links", len(links))
        return list(links)

    def get_normalized_html(self) -> str:
        # Return prettified HTML – useful for downstream processing or storage.
        normalized = self.soup.prettify()
        logger.debug("Normalized HTML length: %d characters", len(normalized))
        return normalized
