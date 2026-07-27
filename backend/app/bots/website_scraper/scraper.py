import logging
import asyncio
from typing import Dict, Any, List, Optional

from .crawler import Crawler
from .parser import HTMLParser
from .contact_extractor import (
    extract_emails,
    extract_phones,
    extract_address,
    find_contact_page,
    find_about_page,
    find_privacy_policy,
    find_terms_page,
    extract_contact_form,
)
from .metadata_extractor import MetadataExtractor
from .social_extractor import SocialExtractor
from .technology_detector import TechnologyDetector

logger = logging.getLogger(__name__)


class WebsiteScraper:
    """High‑level orchestrator for the Website Scraper Bot.

    The class provides a single public async method ``scrape`` that accepts a
    website URL and returns a comprehensive JSON‑serialisable dictionary with all
    extracted information defined in the SRS.
    """

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        timeout: int = 30000,
        max_retries: int = 3,
    ) -> None:
        self.headless = headless
        self.slow_mo = slow_mo
        self.timeout = timeout
        self.max_retries = max_retries
        self.crawler = Crawler(
            headless=headless, slow_mo=slow_mo, timeout=timeout, max_retries=max_retries
        )

    async def _process_html(self, html: str, final_url: str) -> Dict[str, Any]:
        """Parse HTML and run all extractor modules."""
        parser = HTMLParser(html, final_url)
        
        # Basic parsing results
        title = parser.get_title()

        # Contact information
        emails = list(extract_emails(html))
        phones = list(extract_phones(html))
        address = extract_address(html)
        contact_form_exists, contact_form_fields = extract_contact_form(parser.soup)
        
        # Page finders
        contact_page = find_contact_page(parser.soup, final_url)
        about_page = find_about_page(parser.soup, final_url)
        privacy_policy = find_privacy_policy(parser.soup, final_url)
        terms_page = find_terms_page(parser.soup, final_url)

        # Metadata extraction
        metadata = MetadataExtractor(parser.soup, final_url).as_dict()

        # Social media links
        social = SocialExtractor(html).extract()

        # Technology detection
        technologies = TechnologyDetector(html).detect()

        # Construct flat social links
        social_links = {
            "facebook": social.get("facebook")[0] if social.get("facebook") else None,
            "instagram": social.get("instagram")[0] if social.get("instagram") else None,
            "linkedin": social.get("linkedin")[0] if social.get("linkedin") else None,
            "twitter": social.get("twitter")[0] if social.get("twitter") else None,
            "youtube": social.get("youtube")[0] if social.get("youtube") else None,
            "tiktok": social.get("tiktok")[0] if social.get("tiktok") else None,
            "whatsapp": social.get("whatsapp")[0] if social.get("whatsapp") else None,
        }

        return {
            "title": title or metadata.get("title") or "",
            "company_name": metadata.get("company_name") or title or "",
            "meta_description": metadata.get("meta_description") or "",
            "emails": emails,
            "phones": phones,
            "address": address,
            "contact_page": contact_page,
            "about_page": about_page,
            "privacy_policy": privacy_policy,
            "terms_page": terms_page,
            "social_links": social_links,
            "contact_form": contact_form_exists,
            "fields": contact_form_fields,
            "technologies": technologies,
            "language": metadata.get("language") or "en",
            "favicon": metadata.get("favicon"),
            "logo": metadata.get("logo"),
            "canonical": metadata.get("canonical_url"),
        }

    async def scrape(self, url: str) -> Dict[str, Any]:
        """Public entry point – fetch the page and aggregate all extracted data."""
        # Ensure we have http:// or https:// prefix
        normalized_url = url.strip()
        if not normalized_url.startswith(("http://", "https://")):
            normalized_url = "https://" + normalized_url

        logger.info("Starting scrape for %s", normalized_url)
        try:
            html, final_url = await self.crawler.fetch(normalized_url)
        except Exception as exc:
            logger.exception("Exception during fetch for %s", normalized_url)
            return {
                "status": "failed",
                "error": str(exc)
            }

        if html is None or final_url is None:
            logger.error("Failed to fetch %s after retries", normalized_url)
            return {
                "status": "failed",
                "error": f"Unable to retrieve page after {self.max_retries} attempts. Check logs for details.",
            }

        try:
            result = await self._process_html(html, final_url)
            result.update({
                "website": final_url or normalized_url,
                "status": "success",
            })
            return result
        except Exception as exc:  # noqa: BLE001 – capture any parsing/runtime error.
            logger.exception("Error processing HTML for %s", final_url)
            return {
                "status": "failed",
                "error": str(exc)
            }

    # Convenience synchronous wrapper for FastAPI endpoints that prefer a regular function.
    def scrape_sync(self, url: str) -> Dict[str, Any]:
        """Run the async ``scrape`` method in an event loop for sync callers.
        """
        return asyncio.run(self.scrape(url))

# Example FastAPI integration (optional – the router can import and use this class)
# from fastapi import APIRouter, HTTPException
# router = APIRouter()
#
# @router.post("/scrape")
# async def scrape_endpoint(payload: dict):
#     url = payload.get("website")
#     if not url:
#         raise HTTPException(status_code=400, detail="'website' field required")
#     scraper = WebsiteScraper()
#     return await scraper.scrape(url)
