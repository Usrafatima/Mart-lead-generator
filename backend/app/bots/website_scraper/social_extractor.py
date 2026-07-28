import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOCIAL_DOMAINS = {
    "facebook": ["facebook.com", "fb.com"],
    "instagram": ["instagram.com"],
    "linkedin": ["linkedin.com"],
    "whatsapp": ["wa.me", "whatsapp.com", "api.whatsapp.com"],
    "twitter": ["twitter.com", "x.com"],
    "pinterest": ["pinterest.com"],
    "youtube": ["youtube.com", "youtu.be"],
    "tiktok": ["tiktok.com"],
}

# Subpaths that indicate sharing, login, plugins, or non-profile pages
EXCLUDED_PATTERNS = [
    re.compile(r"facebook\.com\/(?:sharer|share|dialog|login|plugins|v\d+\.\d+|policies|legal|help|about|home|privacy|terms)", re.I),
    re.compile(r"twitter\.com\/(?:intent|share|home|search|hashtag|i\/)", re.I),
    re.compile(r"x\.com\/(?:intent|share|home|search|hashtag|i\/)", re.I),
    re.compile(r"linkedin\.com\/(?:shareArticle|sharing|legal|help|privacy|signup)", re.I),
    re.compile(r"instagram\.com\/(?:p\/|reel\/|stories\/|accounts\/|explore\/)", re.I),
    re.compile(r"pinterest\.com\/pin\/create", re.I),
    re.compile(r"youtube\.com\/(?:watch|embed|shorts|playlist|share)", re.I),
]


class SocialExtractor:
    """Extract real social media profile/page URLs from a page's HTML, ignoring share/login links."""

    def __init__(self, html: str):
        self.soup = BeautifulSoup(html, "lxml")

    def _match_platform(self, href: str) -> str | None:
        for platform, domains in SOCIAL_DOMAINS.items():
            for domain in domains:
                if domain in href:
                    return platform
        return None

    def _is_valid_profile_link(self, href: str) -> bool:
        # Check against exclusion rules
        for pattern in EXCLUDED_PATTERNS:
            if pattern.search(href):
                return False
        
        # Ensure path is not just root or empty for main platforms
        parsed = urlparse(href)
        path = parsed.path.strip("/")
        
        if "facebook.com" in parsed.netloc or "fb.com" in parsed.netloc:
            return bool(path or "profile.php" in parsed.path or "pages" in parsed.path)
            
        if "instagram.com" in parsed.netloc:
            return bool(path and len(path) > 1)
            
        if "linkedin.com" in parsed.netloc:
            return bool("company" in path or "in" in path or "pub" in path or path)
            
        if "tiktok.com" in parsed.netloc:
            return bool(path.startswith("@") or path)
            
        return True

    def extract(self) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {platform: [] for platform in SOCIAL_DOMAINS}
        for a in self.soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href:
                continue
            
            platform = self._match_platform(href.lower())
            if platform and self._is_valid_profile_link(href):
                parsed = urlparse(href)
                norm = f"{parsed.scheme or 'https'}://{parsed.netloc}{parsed.path}".rstrip('/')
                if parsed.query and ("profile.php" in parsed.path or "phone" in parsed.query):
                    norm = f"{norm}?{parsed.query}"
                    
                if norm not in result[platform]:
                    result[platform].append(norm)
                    
        cleaned = {k: v for k, v in result.items() if v}
        logger.debug("Filtered social profile links extracted: %s", cleaned)
        return cleaned
