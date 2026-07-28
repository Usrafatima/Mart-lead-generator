"""
Bridge between the Google Maps Discovery Bot and the database.

The bot (app/bots/google_maps.py) scrapes a city and hands back a list of
BusinessLead dataclasses. This module persists them and automatically queues
the website enrichment pipeline for each saved business AFTER db.commit().
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.core.assignments import intern_for_city
from app.models.business import Business
from app.models.lead import Lead, AutomationStatus
from app.services.dedup import upsert_business
from app.services.reports import current_week_number

logger = logging.getLogger(__name__)


def _value(lead: Any, field: str) -> Optional[Any]:
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
    """
    name = _clean(_value(scraped, "name"))
    if not name:
        logger.warning("Skipping scraped result with no business name")
        return None, False

    city = _clean(_value(scraped, "city"))
    country = _clean(_value(scraped, "country"))
    address = _clean(_value(scraped, "address"))

    if address:
        from app.bots.google_maps import GoogleMapsBot
        city, country = GoogleMapsBot._parse_address_components(address, city or "", country)

    business = Business(
        name=name,
        city=city,
        country=country,
        business_type=_clean(_value(scraped, "category")),
        address=address,
        phone=_clean(_value(scraped, "phone")),
        website=_clean(_value(scraped, "website")),
        rating=_value(scraped, "google_rating"),
        reviews_count=_value(scraped, "reviews_count"),
        place_id=_clean(_value(scraped, "place_id")),
        maps_url=_clean(_value(scraped, "maps_url")),
        source_bot=_clean(_value(scraped, "source")) or "google_maps_bot",
        assigned_to=assigned_to or intern_for_city(city),
    )

    business, created = upsert_business(db, business, commit=False)

    if create_lead:
        db.flush()
        lead = db.query(Lead).filter(Lead.business_id == business.id).first()
        if lead is None:
            lead = Lead(
                business_id=business.id,
                week_number=week_number if week_number is not None else current_week_number(),
            )
            db.add(lead)

        if business.website and business.website.strip():
            lead.automation_status = AutomationStatus.in_progress
            lead.automation_status_detail = "Queued"
        else:
            lead.automation_status = AutomationStatus.completed
            lead.automation_status_detail = "Skipped (No Website)"

    return business, created


def ingest_scraped_leads(
    db: Session,
    scraped: Iterable[Any],
    *,
    assigned_to: Optional[str] = None,
    week_number: Optional[int] = None,
    commit: bool = True,
) -> dict:
    """Persist a whole scrape run. Queues enrichment tasks AFTER DB commit."""
    created = merged = skipped = 0
    businesses_to_enrich = []

    for item in scraped:
        business, was_created = ingest_scraped_lead(
            db, item, assigned_to=assigned_to, week_number=week_number
        )
        if business is None:
            skipped += 1
        else:
            if was_created:
                created += 1
            else:
                merged += 1
            if business.website and business.website.strip():
                businesses_to_enrich.append(business)

    if commit:
        db.commit()
        logger.info("[DiscoveryIngest] DB transaction committed for %d businesses.", len(scraped))

        # Enqueue enrichment tasks AFTER db.commit() so database rows exist for Celery worker
        for biz in businesses_to_enrich:
            biz_id_str = str(biz.id)
            logger.info("[DiscoveryIngest] Dispatching enrichment for business '%s' (ID: %s)", biz.name, biz_id_str)
            try:
                from app.workers.celery_worker import enrich_website_task
                enrich_website_task.delay(biz_id_str)
                logger.info("[DiscoveryIngest] Successfully queued Celery task for %s", biz.name)
            except Exception as err:
                logger.warning("[DiscoveryIngest] Celery queue error for %s: %s. Launching background fallback thread.", biz.name, err)
                def _fallback_enrich(target_id: str):
                    try:
                        from app.workers.celery_worker import enrich_website_task
                        enrich_website_task(target_id)
                    except Exception as f_err:
                        logger.error("[DiscoveryIngest] Fallback enrichment failed for %s: %s", target_id, f_err)
                threading.Thread(target=_fallback_enrich, args=(biz_id_str,), daemon=True).start()

    summary = {"created": created, "merged_as_duplicate": merged, "skipped": skipped}
    logger.info("Discovery ingest finished: %s", summary)
    return summary
