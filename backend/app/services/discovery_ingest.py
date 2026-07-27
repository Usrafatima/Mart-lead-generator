"""
Bridge between the Google Maps Discovery Bot and the database.

The bot (app/bots/google_maps.py) scrapes a city and hands back a list of
BusinessLead dataclasses — its own docstring notes that it's left to "whoever
wires up the DB / API integration" to persist them. That's this module.

Everything lands through upsert_business(), so scraping the same city twice, or
two interns scraping overlapping areas, merges rather than inflating the lead
count. This is what makes adding a new city a one-command operation.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.core.assignments import intern_for_city
from app.models.business import Business
from app.models.lead import Lead
from app.services.dedup import upsert_business
from app.services.reports import current_week_number

logger = logging.getLogger(__name__)


def _value(lead: Any, field: str) -> Optional[Any]:
    """Read a field from a BusinessLead dataclass or a plain dict."""
    if isinstance(lead, dict):
        return lead.get(field)
    return getattr(lead, field, None)


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def ingest_scraped_lead(
    db: Session,
    scraped: Any,
    *,
    assigned_to: Optional[str] = None,
    week_number: Optional[int] = None,
    create_lead: bool = True,
) -> tuple[Optional[Business], bool]:
    """
    Persist one scraped business.

    Returns (business, created). `created` is False when it matched something
    already in the database — callers can use that to skip re-queuing AI
    classification for a business that's already been through it.
    """
    name = _clean(_value(scraped, "name"))
    if not name:
        logger.warning("Skipping scraped result with no business name")
        return None, False

    city = _clean(_value(scraped, "city"))

    business = Business(
        name=name,
        city=city,
        country=_clean(_value(scraped, "country")),
        business_type=_clean(_value(scraped, "category")),
        address=_clean(_value(scraped, "address")),
        phone=_clean(_value(scraped, "phone")),
        website=_clean(_value(scraped, "website")),
        rating=_value(scraped, "google_rating"),
        reviews_count=_value(scraped, "reviews_count"),
        place_id=_clean(_value(scraped, "place_id")),
        maps_url=_clean(_value(scraped, "maps_url")),
        source_bot=_clean(_value(scraped, "source")) or "google_maps_bot",
        # The bot only knows which city it searched, not who asked for it, so
        # fall back to the assignment table.
        assigned_to=assigned_to or intern_for_city(city),
    )

    business, created = upsert_business(db, business, commit=False)

    if create_lead:
        db.flush()  # need business.id
        lead = db.query(Lead).filter(Lead.business_id == business.id).first()
        if lead is None:
            # Created unclassified — the AI Classification Service fills in
            # order method, priority and notes later via its own endpoint.
            lead = Lead(
                business_id=business.id,
                week_number=week_number if week_number is not None else current_week_number(),
            )
            db.add(lead)

    return business, created


def ingest_scraped_leads(
    db: Session,
    scraped: Iterable[Any],
    *,
    assigned_to: Optional[str] = None,
    week_number: Optional[int] = None,
    commit: bool = True,
) -> dict:
    """Persist a whole scrape run. Returns a summary."""
    created = merged = skipped = 0

    for item in scraped:
        business, was_created = ingest_scraped_lead(
            db, item, assigned_to=assigned_to, week_number=week_number
        )
        if business is None:
            skipped += 1
        elif was_created:
            created += 1
        else:
            merged += 1

    if commit:
        db.commit()

    summary = {"created": created, "merged_as_duplicate": merged, "skipped": skipped}
    logger.info("Discovery ingest finished: %s", summary)
    return summary
