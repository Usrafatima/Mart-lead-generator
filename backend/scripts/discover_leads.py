"""
Scrape a city with the Google Maps bot and load the results straight into
PostgreSQL, de-duplicated.

This is the "add a new city" command — nothing is hardcoded per city, so a
new market is a new argument, not a code change:

    python -m scripts.discover_leads --city "Karachi" --category "supermarket"
    python -m scripts.discover_leads --city "Riyadh" --category "grocery store" --max 40
    python -m scripts.discover_leads --city "Bristol" --category "mini mart" --assigned-to Haifa

Run it repeatedly and safely: results are matched against what's already in
the database (by Google place_id first, then phone/domain/name) and merged
instead of duplicated.

Needs Playwright browsers installed:

    pip install -r requirements.txt
    playwright install chromium
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.core.assignments import intern_for_city
from app.core.database import SessionLocal
from app.services.discovery_ingest import ingest_scraped_leads


async def _scrape(category: str, city: str, country: str | None, max_results: int, headless: bool):
    """Run the teammate-owned Maps bot. Imported lazily so this script still
    loads (and --help works) on a machine without Playwright installed."""
    from app.bots.google_maps import GoogleMapsBot

    bot = GoogleMapsBot(headless=headless)
    return await bot.search_businesses(
        category=category,
        city=city,
        country=country,
        max_results=max_results,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover businesses in a city and store them in the database"
    )
    parser.add_argument("--city", required=True, help='City to search, e.g. "Karachi"')
    parser.add_argument(
        "--category",
        default="supermarket",
        help='Business category to search for, e.g. "grocery store"',
    )
    parser.add_argument("--country", default=None, help='Optional country, e.g. "Pakistan"')
    parser.add_argument("--max", type=int, default=30, help="Maximum results to collect")
    parser.add_argument(
        "--assigned-to",
        default=None,
        help="Intern to credit. Defaults to whoever owns the city in the assignment table.",
    )
    parser.add_argument(
        "--week",
        type=int,
        default=None,
        help="ISO week to record. Defaults to the current week.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and match, then roll back without saving",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Run with a visible browser window, for debugging the scrape",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    owner = args.assigned_to or intern_for_city(args.city)
    if owner is None:
        # Not fatal — new cities won't be in the assignment table yet — but
        # unattributed leads don't show up on anyone's weekly target.
        print(
            f"Note: '{args.city}' isn't in the assignment table, so these leads "
            f"won't count towards an intern's weekly target. "
            f"Pass --assigned-to NAME to credit someone, or add the city to "
            f"app/core/assignments.py.",
            file=sys.stderr,
        )

    try:
        scraped = asyncio.run(
            _scrape(args.category, args.city, args.country, args.max, not args.show_browser)
        )
    except ImportError as exc:
        print(
            f"Could not load the Google Maps bot: {exc}\n"
            "Install scraping dependencies first:\n"
            "    pip install -r requirements.txt\n"
            "    playwright install chromium",
            file=sys.stderr,
        )
        return 1

    print(f"Scraped {len(scraped)} result(s) for '{args.category}' in {args.city}")

    db = SessionLocal()
    try:
        summary = ingest_scraped_leads(
            db,
            scraped,
            assigned_to=owner,
            week_number=args.week,
            commit=not args.dry_run,
        )
        if args.dry_run:
            db.rollback()
            print("DRY RUN — nothing was saved")

        print(
            f"new={summary['created']} "
            f"merged_with_existing={summary['merged_as_duplicate']} "
            f"skipped={summary['skipped']}"
        )
        return 0

    except Exception as exc:
        db.rollback()
        print(f"Ingest failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
