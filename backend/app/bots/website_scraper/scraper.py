import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse

from .crawler import Crawler
from .parser import HTMLParser
from .contact_extractor import (
    extract_emails,
    extract_phones,
    extract_address,
    extract_owner_name,
    find_contact_page,
    find_about_page,
    extract_contact_form,
)
from .social_extractor import SocialExtractor
from .technology_detector import TechnologyDetector

logger = logging.getLogger(__name__)

SOCIAL_ONLY_DOMAINS = {
    "facebook.com", "fb.com", "instagram.com", "linktr.ee", "wa.me",
    "whatsapp.com", "tiktok.com", "twitter.com", "x.com"
}


class WebsiteScraper:
    """High-level orchestrator for Website & Social Media Scraping."""

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        timeout: int = 25000,
        max_retries: int = 3,
    ) -> None:
        self.headless = headless
        self.slow_mo = slow_mo
        self.timeout = timeout
        self.max_retries = max_retries
        self.crawler = Crawler(
            headless=headless, slow_mo=slow_mo, timeout=timeout, max_retries=max_retries
        )

    def _check_is_social_only(self, url: str) -> Tuple[bool, Optional[str]]:
        parsed = urlparse(url.lower())
        netloc = parsed.netloc.replace("www.", "").replace("m.", "")
        for domain in SOCIAL_ONLY_DOMAINS:
            if domain in netloc:
                return True, domain
        return False, None

    async def scrape(self, url: str) -> Dict[str, Any]:
        """Scrape primary page + discovered contact/about pages for contact/social info."""
        normalized_url = url.strip()
        if not normalized_url.startswith(("http://", "https://")):
            normalized_url = "https://" + normalized_url

        is_social_only, social_domain = self._check_is_social_only(normalized_url)
        logger.info("[WebsiteScraper] Starting scrape for %s (Social Only: %s)", normalized_url, is_social_only)

        pages_html, primary_url, error_reason = await self.crawler.crawl_url(normalized_url)

        if not pages_html or not primary_url:
            logger.error("[WebsiteScraper] Could not retrieve pages for %s. Reason: %s", normalized_url, error_reason)
            return {
                "status": "failed",
                "error": error_reason or "Failed to retrieve website pages",
            }

        all_emails = set()
        all_phones = set()
        all_socials: Dict[str, str] = {}
        all_techs = set()
        all_providers = set()
        owner_name = None
        contact_page_url = None
        contact_form_found = False

        primary_html = pages_html.get(primary_url, "")

        for page_url, html in pages_html.items():
            parser = HTMLParser(html, page_url)

            # Emails and Phones (decoded, validated & deduped)
            all_emails.update(extract_emails(html))
            all_phones.update(extract_phones(html))

            # Owner / Manager Name (JSON-LD, meta, text patterns)
            if not owner_name:
                owner_name = extract_owner_name(html, parser.soup)

            # Contact Page
            if not contact_page_url:
                contact_page_url = find_contact_page(parser.soup, page_url)

            # Contact Form
            has_form, _ = extract_contact_form(parser.soup)
            if has_form:
                contact_form_found = True

            # Filtered Social links (no share/login URLs)
            social = SocialExtractor(html).extract()
            for platform, links in social.items():
                if platform not in all_socials and links:
                    all_socials[platform] = links[0]

            # Tech & Delivery detection
            tech_detector = TechnologyDetector(html)
            all_techs.update(tech_detector.detect())
            all_providers.update(tech_detector.detect_delivery_providers())

        # Determine order method and delivery system details
        primary_detector = TechnologyDetector(primary_html)
        order_method, order_method_detail, delivery_system = primary_detector.detect_order_and_delivery()
        if all_providers:
            delivery_system = ", ".join(sorted(all_providers))

        if is_social_only:
            order_method_detail = f"Social Only ({social_domain.capitalize()})"
            all_techs.add("Social Only")

        social_links = {
            "facebook": all_socials.get("facebook"),
            "instagram": all_socials.get("instagram"),
            "linkedin": all_socials.get("linkedin"),
            "twitter": all_socials.get("twitter"),
            "youtube": all_socials.get("youtube"),
            "tiktok": all_socials.get("tiktok"),
            "whatsapp": all_socials.get("whatsapp"),
        }

        logger.info(
            "[WebsiteScraper] Success for %s — Emails: %d (%s), Socials: %d, Owner: %s",
            primary_url,
            len(all_emails),
            list(all_emails),
            len([v for v in social_links.values() if v]),
            owner_name or "None",
        )

        return {
            "status": "success",
            "website": primary_url,
            "website_type": "Social Only" if is_social_only else "Website",
            "emails": sorted(list(all_emails)),
            "phones": sorted(list(all_phones)),
            "owner_manager_name": owner_name,
            "contact_page": contact_page_url,
            "contact_form": contact_form_found,
            "social_links": social_links,
            "technologies": sorted(list(all_techs)),
            "delivery_providers": sorted(list(all_providers)),
            "order_method": order_method,
            "order_method_detail": order_method_detail,
            "delivery_system": delivery_system,
            "pages_crawled": len(pages_html),
        }

    def scrape_sync(self, url: str) -> Dict[str, Any]:
        """Synchronous wrapper around scrape."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()

        return loop.run_until_complete(self.scrape(url))
