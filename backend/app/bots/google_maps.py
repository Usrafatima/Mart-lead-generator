"""
Google Maps Discovery Bot
==========================
Role: Google Maps Discovery Bot (independent module)

What it does
------------
- Searches Google Maps for a given business category + city
- Collects: name, address, phone, website, rating, reviews count, category
- Removes duplicate businesses (by Google place identifier, falls back to
  name+address if a place id can't be parsed)
- Exports results to CSV / JSON, or returns a plain Python list so other
  modules (DB layer, API layer, AI classifier) can consume it directly

This module has NO dependency on the database, FastAPI, or Celery — it can
be developed, tested, and run completely on its own. Whoever owns the
"Database & Google Sheets Integration" or "Backend API Development" part
can simply import `GoogleMapsBot` and `BusinessLead` and wire it in.

Usage (standalone test)
------------------------
    pip install playwright beautifulsoup4
    playwright install chromium

    python -m app.bots.google_maps --category "grocery stores" --city "Lahore" --max 30 --out leads.csv

Usage (as a library)
---------------------
    from app.bots.google_maps import GoogleMapsBot

    bot = GoogleMapsBot(headless=True)
    leads = await bot.search_businesses("restaurants", "Karachi", max_results=50)

Notes / limitations
--------------------
- Google Maps DOM/attributes change over time. Selectors below prefer
  `aria-label` / `data-item-id` attributes (more stable than CSS class
  names), but they may still need small tweaks periodically.
- For large-scale / production scraping, consider adding proxy rotation
  and randomized delays to avoid rate-limiting/CAPTCHAs, or switching to
  the official Google Places API for higher reliability (trade-off:
  costs money and has different data fields).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Set

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("google_maps_bot")

GOOGLE_MAPS_SEARCH_URL = "https://www.google.com/maps/search/{query}"


@dataclass
class BusinessLead:
    """Structured result for one scraped business."""

    name: str
    category: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    google_rating: Optional[float] = None
    reviews_count: Optional[int] = None
    maps_url: Optional[str] = None
    place_id: Optional[str] = None
    source: str = "google_maps"

    def dedupe_key(self) -> str:
        """Key used to detect duplicate businesses across a scrape run."""
        if self.place_id:
            return f"pid:{self.place_id}"
        return f"na:{(self.name or '').strip().lower()}|{(self.address or '').strip().lower()}"


class GoogleMapsBot:
    """Playwright-driven Google Maps business discovery bot."""

    def __init__(self, headless: bool = True, slow_mo: int = 0, nav_timeout_ms: int = 30000):
        self.headless = headless
        self.slow_mo = slow_mo
        self.nav_timeout_ms = nav_timeout_ms

    async def search_businesses(
        self,
        category: str,
        city: str,
        country: Optional[str] = None,
        max_results: int = 50,
    ) -> List[BusinessLead]:
        """Search Google Maps and return a de-duplicated list of BusinessLead."""
        location = f"{city}, {country}" if country else city
        query = f"{category} in {location}"
        logger.info("Searching Google Maps for: %s", query)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
            context = await browser.new_context(
                locale="en-US",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()
            page.set_default_timeout(self.nav_timeout_ms)

            try:
                search_url = GOOGLE_MAPS_SEARCH_URL.format(query=query.replace(" ", "+"))
                await page.goto(search_url, wait_until="domcontentloaded")
                await self._dismiss_consent_dialog(page)

                place_links = await self._collect_place_links(page, max_results)
                logger.info("Found %d candidate listings, extracting details...", len(place_links))

                leads: List[BusinessLead] = []
                seen_keys: Set[str] = set()

                for i, link in enumerate(place_links, start=1):
                    try:
                        lead = await self._extract_business_details(page, link, city, country)
                    except PlaywrightTimeoutError:
                        logger.warning("Timed out extracting details for %s", link)
                        continue
                    except Exception as exc:  # noqa: BLE001 - keep scraping other listings
                        logger.warning("Failed to extract %s: %s", link, exc)
                        continue

                    if not lead or not lead.name:
                        continue

                    key = lead.dedupe_key()
                    if key in seen_keys:
                        logger.debug("Skipping duplicate: %s", lead.name)
                        continue
                    seen_keys.add(key)

                    lead.category = lead.category or category
                    leads.append(lead)
                    logger.info("[%d/%d] Collected: %s", i, len(place_links), lead.name)

                logger.info("Done. %d unique businesses collected.", len(leads))
                return leads
            finally:
                await context.close()
                await browser.close()

    async def _dismiss_consent_dialog(self, page: Page) -> None:
        """Handle the EU/region cookie-consent screen if Google shows one."""
        for text in ["Accept all", "I agree", "Reject all"]:
            try:
                btn = page.get_by_role("button", name=text)
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    return
            except Exception:
                continue

    async def _collect_place_links(self, page: Page, max_results: int) -> List[str]:
        """Scroll the results feed and collect unique /maps/place/ links."""
        try:
            feed = page.locator('div[role="feed"]')
            await feed.wait_for(timeout=15000)
        except PlaywrightTimeoutError:
            logger.warning("Results feed not found (layout change, or zero results for this search).")
            return []

        collected: Dict[str, None] = {}
        stagnant_rounds = 0
        max_stagnant_rounds = 4  # stop once scrolling stops producing new links

        while len(collected) < max_results and stagnant_rounds < max_stagnant_rounds:
            before = len(collected)
            anchors = await feed.locator('a[href*="/maps/place/"]').all()
            for anchor in anchors:
                href = await anchor.get_attribute("href")
                if href:
                    collected[href] = None
                if len(collected) >= max_results:
                    break

            stagnant_rounds = stagnant_rounds + 1 if len(collected) == before else 0

            await feed.evaluate("(el) => el.scrollBy(0, el.scrollHeight)")
            await page.wait_for_timeout(1500)

        return list(collected.keys())[:max_results]

    async def _extract_business_details(
        self, page: Page, place_url: str, city: str, country: Optional[str]
    ) -> Optional[BusinessLead]:
        """Open a place detail page in a new tab and extract structured fields."""
        detail_page = await page.context.new_page()
        try:
            await detail_page.goto(place_url, wait_until="domcontentloaded")
            await detail_page.wait_for_selector("h1", timeout=15000)

            name = (await detail_page.locator("h1").first.inner_text()).strip()

            category = None
            try:
                category = (
                    await detail_page.locator('button[jsaction*="category"]').first.inner_text()
                ).strip()
            except Exception:
                pass

            rating, reviews_count = await self._extract_rating_and_reviews(detail_page)
            address = await self._get_field_by_item_id(detail_page, "address", label_prefix="Address: ")
            phone = await self._get_field_by_item_id(detail_page, "phone", label_prefix="Phone: ")

            website = None
            try:
                website = await detail_page.locator('a[data-item-id="authority"]').first.get_attribute("href")
            except Exception:
                pass

            place_id = self._parse_place_id(place_url)

            return BusinessLead(
                name=name,
                category=category,
                address=address,
                city=city,
                country=country,
                phone=phone,
                website=website,
                google_rating=rating,
                reviews_count=reviews_count,
                maps_url=place_url,
                place_id=place_id,
            )
        finally:
            await detail_page.close()

    async def _extract_rating_and_reviews(self, page: Page):
        rating, reviews_count = None, None
        try:
            rating_text = await page.locator('div.F7nice span[aria-hidden="true"]').first.inner_text()
            rating = float(rating_text.replace(",", "."))
        except Exception:
            pass
        try:
            reviews_label = await page.locator(
                'div.F7nice span[aria-label*="review"]'
            ).first.get_attribute("aria-label")
            if reviews_label:
                digits = re.sub(r"[^\d]", "", reviews_label)
                reviews_count = int(digits) if digits else None
        except Exception:
            pass
        return rating, reviews_count

    async def _get_field_by_item_id(self, page: Page, item_id_prefix: str, label_prefix: str) -> Optional[str]:
        try:
            el = page.locator(f'button[data-item-id^="{item_id_prefix}"]').first
            aria = await el.get_attribute("aria-label")
            if not aria:
                return None
            return aria[len(label_prefix):].strip() if aria.startswith(label_prefix) else aria.strip()
        except Exception:
            return None

    @staticmethod
    def _parse_place_id(place_url: str) -> Optional[str]:
        match = re.search(r"!1s([^!]+)", place_url)
        return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def leads_to_dicts(leads: List[BusinessLead]) -> List[dict]:
    """Plain JSON-serializable list of dicts — handy for whoever wires up
    the DB / API integration; they can just json.dumps() or feed straight
    into a Pydantic model / SQLAlchemy insert."""
    return [asdict(lead) for lead in leads]


def export_to_csv(leads: List[BusinessLead], filepath: str) -> None:
    if not leads:
        logger.warning("No leads to export.")
        return
    fieldnames = list(asdict(leads[0]).keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            writer.writerow(asdict(lead))
    logger.info("Exported %d leads to %s", len(leads), filepath)


def export_to_json(leads: List[BusinessLead], filepath: str) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([asdict(lead) for lead in leads], f, indent=2, ensure_ascii=False)
    logger.info("Exported %d leads to %s", len(leads), filepath)


# ---------------------------------------------------------------------------
# CLI entry point (for standalone testing)
# ---------------------------------------------------------------------------

async def _run_cli() -> None:
    parser = argparse.ArgumentParser(description="Google Maps Discovery Bot")
    parser.add_argument("--category", required=True, help="Business category, e.g. 'grocery stores'")
    parser.add_argument("--city", required=True, help="City to search in, e.g. 'Lahore'")
    parser.add_argument("--country", default=None, help="Optional country, e.g. 'Pakistan'")
    parser.add_argument("--max", type=int, default=30, dest="max_results")
    parser.add_argument("--no-headless", action="store_true", help="Show the browser window")
    parser.add_argument("--out", default="leads.json", help="Output file: .json (default) or .csv")
    args = parser.parse_args()

    bot = GoogleMapsBot(headless=not args.no_headless)
    leads = await bot.search_businesses(
        category=args.category,
        city=args.city,
        country=args.country,
        max_results=args.max_results,
    )

    if args.out.endswith(".json"):
        export_to_json(leads, args.out)
    else:
        export_to_csv(leads, args.out)


if __name__ == "__main__":
    asyncio.run(_run_cli())
