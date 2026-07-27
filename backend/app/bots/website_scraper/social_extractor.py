import logging
from typing import Dict, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOCIAL_DOMAINS = {
    "facebook": ["facebook.com", "fb.com"],
    "instagram": ["instagram.com"],
    "linkedin": ["linkedin.com"],
    "whatsapp": ["wa.me", "whatsapp.com"],
    "twitter": ["twitter.com", "x.com"],
    "pinterest": ["pinterest.com"],
    "youtube": ["youtube.com", "youtu.be"],
    "tiktok": ["tiktok.com"],
}


class SocialExtractor:
    """Extract social media profile/page URLs from a page's HTML.

    The extractor scans ``<a>`` tags for hrefs that contain known social platform
    domains. It normalises the URLs (removing trailing slashes) and groups them by
    platform.
    """

    def __init__(self, html: str):
        self.soup = BeautifulSoup(html, "lxml")

    def _match_platform(self, href: str) -> str | None:
        for platform, domains in SOCIAL_DOMAINS.items():
            for domain in domains:
                if domain in href:
                    return platform
        return None

    def extract(self) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {platform: [] for platform in SOCIAL_DOMAINS}
        for a in self.soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href:
                continue
            platform = self._match_platform(href.lower())
            if platform:
                # Normalise
                parsed = urlparse(href)
                norm = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
                if norm not in result[platform]:
                    result[platform].append(norm)
        # Remove empty entries
        cleaned = {k: v for k, v in result.items() if v}
        logger.debug("Social links extracted: %s", cleaned)
        return cleaned
