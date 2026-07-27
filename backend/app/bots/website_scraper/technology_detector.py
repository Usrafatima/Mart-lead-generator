import logging
import re
from typing import List, Dict
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Simple detection patterns for each technology/platform.
_DETECTION_PATTERNS: Dict[str, List[re.Pattern]] = {
    "wordpress": [re.compile(r"wp-content", re.I), re.compile(r"wordpress", re.I)],
    "woocommerce": [re.compile(r"woocommerce", re.I)],
    "shopify": [re.compile(r"cdn\.shopify\.com", re.I), re.compile(r"shopify\.myshopify\.com", re.I)],
    "magento": [re.compile(r"mage\/cache", re.I), re.compile(r"magento", re.I)],
    "react": [re.compile(r"react\.js", re.I), re.compile(r"data-reactroot", re.I)],
    "next.js": [re.compile(r"__next", re.I), re.compile(r"next\.data", re.I)],
    "vue": [re.compile(r"vue\.js", re.I), re.compile(r"data-vue", re.I)],
    "angular": [re.compile(r"angular\.js", re.I), re.compile(r"ng-version", re.I)],
    "laravel": [re.compile(r"laravel", re.I), re.compile(r"csrf-token", re.I)],
    "flask": [re.compile(r"flask", re.I)],
    "django": [re.compile(r"django", re.I), re.compile(r"csrfmiddlewaretoken", re.I)],
    "cloudflare": [re.compile(r"cloudflare", re.I), re.compile(r"cf[-_]\w+", re.I)],
    "google_analytics": [re.compile(r"google-analytics\.com", re.I), re.compile(r"gtag\(.+\)", re.I)],
    "facebook_pixel": [re.compile(r"fbq\(.+\)", re.I), re.compile(r"facebook\.net", re.I)],
    "tailwind css": [re.compile(r"tailwind", re.I)],
}


class TechnologyDetector:
    """Detect common CMS, frameworks, and analytics/marketing scripts.

    The detection runs on the raw HTML string (or a BeautifulSoup object) and
    returns a list of technology identifiers that were recognised.
    """

    def __init__(self, html: str):
        self.html = html
        self.soup = BeautifulSoup(html, "lxml")

    def _detect_by_pattern(self) -> List[str]:
        detected: List[str] = []
        for tech, patterns in _DETECTION_PATTERNS.items():
            for pat in patterns:
                if pat.search(self.html):
                    detected.append(tech)
                    break
        logger.debug("Technology detection via regex: %s", detected)
        return detected

    def _detect_by_meta(self) -> List[str]:
        metas = {meta.get('name', '').lower(): meta.get('content', '').lower() for meta in self.soup.find_all('meta') if meta.get('name')}
        detected: List[str] = []
        generator = metas.get('generator', '')
        if "wordpress" in generator:
            detected.append("wordpress")
        if "shopify" in generator:
            detected.append("shopify")
        if "magento" in generator:
            detected.append("magento")
        if "django" in generator:
            detected.append("django")
        if "laravel" in generator:
            detected.append("laravel")
        logger.debug("Technology detection via meta generator: %s", detected)
        return detected

    def detect(self) -> List[str]:
        """Return a deduplicated, human‑readable list of detected technologies.
        """
        raw_set = set(self._detect_by_pattern() + self._detect_by_meta())
        # Mapping to the exact naming required by the SRS.
        name_map = {
            "wordpress": "WordPress",
            "woocommerce": "WooCommerce",
            "shopify": "Shopify",
            "magento": "Magento",
            "react": "React",
            "next.js": "Next.js",
            "vue": "Vue",
            "angular": "Angular",
            "laravel": "Laravel",
            "flask": "Flask",
            "django": "Django",
            "cloudflare": "Cloudflare",
            "google_analytics": "Google Analytics",
            "facebook_pixel": "Facebook Pixel",
            "tailwind css": "Tailwind CSS",
        }
        normalized = [name_map.get(tech, tech.capitalize()) for tech in raw_set]
        logger.info("Detected technologies: %s", normalized)
        return sorted(normalized)
