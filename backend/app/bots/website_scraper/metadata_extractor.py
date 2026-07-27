import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class MetadataExtractor:
    """Extract common SEO and branding metadata from a page's HTML.

    All methods operate on a ``BeautifulSoup`` object created from the page HTML.
    The class is intentionally lightweight – it does not perform network I/O.
    """

    def __init__(self, soup: BeautifulSoup, base_url: str):
        self.soup = soup
        self.base_url = base_url.rstrip('/')

    def _first_content(self, selector: str) -> Optional[str]:
        tag = self.soup.select_one(selector)
        return tag.get("content", "").strip() if tag and tag.get("content") else None

    def extract_title(self) -> str:
        title_tag = self.soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        logger.debug("Metadata title: %s", title)
        return title

    def extract_meta_description(self) -> Optional[str]:
        return self._first_content('meta[name="description"]')

    def extract_canonical_url(self) -> Optional[str]:
        return self._first_content('link[rel="canonical"]')

    def extract_open_graph(self) -> Dict[str, str]:
        og: Dict[str, str] = {}
        for tag in self.soup.select('meta[property^="og:"]'):
            prop = tag.get("property", "").lower()
            content = tag.get("content", "").strip()
            if prop and content:
                og[prop] = content
        logger.debug("OpenGraph tags found: %d", len(og))
        return og

    def extract_twitter(self) -> Dict[str, str]:
        tw: Dict[str, str] = {}
        for tag in self.soup.select('meta[name^="twitter:"]'):
            name = tag.get("name", "").lower()
            content = tag.get("content", "").strip()
            if name and content:
                tw[name] = content
        logger.debug("Twitter tags found: %d", len(tw))
        return tw

    def extract_language(self) -> Optional[str]:
        html_tag = self.soup.find("html")
        if html_tag and html_tag.get("lang"):
            return html_tag["lang"].strip()
        # Fallback to meta http-equiv="content-language"
        return self._first_content('meta[http-equiv="content-language"]')

    def extract_company_name(self) -> Optional[str]:
        # Try common selectors: organization schema, meta author, title parsing.
        org_tag = self.soup.select_one('[itemprop="name"]')
        if org_tag:
            return org_tag.get_text(strip=True)
        author = self._first_content('meta[name="author"]')
        if author:
            return author
        # Fallback: use hostname as a guess.
        try:
            return urlparse(self.base_url).netloc.split(".")[0].capitalize()
        except Exception:
            return None

    def extract_logo(self) -> Optional[str]:
        # Look for schema.org logo or larger sized icons.
        logo_tag = self.soup.select_one('[itemprop="logo"] img')
        if logo_tag and logo_tag.get("src"):
            return urljoin(self.base_url + '/', logo_tag["src"]).rstrip('/')
        # Fallback to larger icons.
        icon = self.soup.select_one('link[rel~="icon"][sizes="180x180"], link[rel~="icon"][sizes="192x192"]')
        if icon and icon.get("href"):
            return urljoin(self.base_url + '/', icon["href"]).rstrip('/')
        return None

    def extract_favicon(self) -> Optional[str]:
        favicon = self.soup.select_one('link[rel~="icon"]')
        if favicon and favicon.get("href"):
            return urljoin(self.base_url + '/', favicon["href"]).rstrip('/')
        return None

    def extract_copyright(self) -> Optional[str]:
        copyright_tag = self.soup.select_one('meta[name="copyright"]')
        if copyright_tag and copyright_tag.get("content"):
            return copyright_tag["content"].strip()
        # Try a generic text search.
        text = self.soup.find(string=lambda t: t and "©" in t)
        return text.strip() if text else None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "title": self.extract_title(),
            "meta_description": self.extract_meta_description(),
            "canonical_url": self.extract_canonical_url(),
            "open_graph": self.extract_open_graph(),
            "twitter": self.extract_twitter(),
            "language": self.extract_language(),
            "company_name": self.extract_company_name(),
            "logo": self.extract_logo(),
            "favicon": self.extract_favicon(),
            "copyright": self.extract_copyright(),
        }
