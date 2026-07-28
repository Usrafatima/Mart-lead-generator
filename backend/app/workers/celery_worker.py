import logging
import time
import uuid
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "leadgen_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "daily-leads-export": {
        "task": "export_leads_csv",
        "schedule": crontab(hour=6, minute=0),
    },
    "daily-dashboard-export": {
        "task": "export_dashboard_csv",
        "schedule": crontab(hour=6, minute=15),
    },
}


@celery_app.task(name="enrich_website_task", bind=True, max_retries=2)
def enrich_website_task(self, business_id: str):
    """
    Website & Social Media enrichment task.
    Crawls website using multi-stage fallback, extracts emails, owner/manager names, social links,
    order methods, delivery providers, and updates existing PostgreSQL records.
    """
    start_time = time.time()
    logger.info("==========================================================")
    logger.info("[EnrichmentTask] STEP 1: Celery worker received task for business_id=%s", business_id)
    from app.core.database import SessionLocal
    from app.models.business import Business
    from app.models.lead import Lead, AutomationStatus, OrderMethod
    from app.bots.website_scraper.scraper import WebsiteScraper
    from app.services.lead_scoring import score_priority
    from app.services.reports import current_week_number

    db = SessionLocal()
    try:
        try:
            b_uuid = uuid.UUID(business_id)
        except ValueError:
            logger.error("[EnrichmentTask] ERROR: Invalid UUID string: %s", business_id)
            return {"status": "error", "reason": "Invalid UUID"}

        business = db.query(Business).filter(Business.id == b_uuid).first()
        if not business:
            logger.error("[EnrichmentTask] ERROR: Business ID %s NOT FOUND in PostgreSQL database!", business_id)
            return {"status": "skipped", "reason": "Business not found in DB"}

        logger.info("[EnrichmentTask] Found Business in DB: name='%s', city='%s', website='%s'", business.name, business.city, business.website)

        lead = db.query(Lead).filter(Lead.business_id == business.id).first()
        if not lead:
            logger.info("[EnrichmentTask] Creating missing Lead record for business_id=%s", business.id)
            lead = Lead(business_id=business.id, week_number=current_week_number())
            db.add(lead)
            db.flush()

        # Skip enrichment gracefully for leads without a website URL
        if not business.website or not business.website.strip():
            logger.info("[EnrichmentTask] STEP 2: Skipping enrichment — Business has no website URL")
            lead.automation_status = AutomationStatus.completed
            lead.automation_status_detail = "Skipped (No Website)"
            db.commit()
            return {"status": "skipped", "reason": "No website URL"}

        # Update status to Processing
        logger.info("[EnrichmentTask] STEP 2: Updating Lead Automation Status to 'Processing'")
        lead.automation_status = AutomationStatus.in_progress
        lead.automation_status_detail = "Processing"
        db.commit()

        # Run WebsiteScraper
        logger.info("[EnrichmentTask] STEP 3: Launching multi-stage scraper for URL: %s", business.website)
        scraper = WebsiteScraper(timeout=25000, max_retries=2)
        result = scraper.scrape_sync(business.website)

        if result.get("status") != "success":
            error_msg = result.get("error", "Website scrape failed")
            logger.error("[EnrichmentTask] STEP 3 FAILED: Scrape failed for %s: %s", business.name, error_msg)

            if self.request.retries < self.max_retries:
                logger.info("[EnrichmentTask] Retrying task (attempt %d/%d)...", self.request.retries + 1, self.max_retries)
                raise self.retry(exc=Exception(error_msg), countdown=5)

            lead.automation_status = AutomationStatus.in_progress
            lead.automation_status_detail = f"Failed ({error_msg[:40]})"
            db.commit()
            
            elapsed = round(time.time() - start_time, 2)
            logger.info("[EnrichmentTask SUMMARY] Lead #%s | Website='%s' | Status='Failed (%s)' | Duration=%.2fs",
                        lead.lead_ref, business.website, error_msg[:30], elapsed)
            return {"status": "failed", "error": error_msg}

        # Step 4: Extract and update Business fields
        logger.info("[EnrichmentTask] STEP 4: Processing extracted website & social data")
        emails = result.get("emails") or []
        logger.info("[EnrichmentTask] Extracted Emails (%d): %s", len(emails), emails)
        if emails and not business.email:
            business.email = emails[0]
            logger.info("[EnrichmentTask] DB UPDATE -> Business.email = %s", business.email)

        owner_name = result.get("owner_manager_name")
        logger.info("[EnrichmentTask] Extracted Owner/Manager Name: %s", owner_name)
        if owner_name and not business.owner_manager_name:
            business.owner_manager_name = owner_name
            logger.info("[EnrichmentTask] DB UPDATE -> Business.owner_manager_name = %s", owner_name)

        social = result.get("social_links") or {}
        logger.info("[EnrichmentTask] Extracted Social Media Links: %s", social)
        if social.get("facebook") and not business.facebook_url:
            business.facebook_url = social.get("facebook")
        if social.get("instagram") and not business.instagram_url:
            business.instagram_url = social.get("instagram")
        if social.get("linkedin") and not business.linkedin_url:
            business.linkedin_url = social.get("linkedin")
        if social.get("whatsapp") and not business.whatsapp_number:
            business.whatsapp_number = social.get("whatsapp")
        if result.get("contact_page") and not business.contact_page_url:
            business.contact_page_url = result.get("contact_page")

        business.set_derived_fields()

        # Step 5: Update Lead fields
        order_method = result.get("order_method")
        order_method_detail = result.get("order_method_detail")
        delivery_sys = result.get("delivery_system")
        logger.info("[EnrichmentTask] Extracted Order Method: %s (%s), Delivery: %s", order_method, order_method_detail, delivery_sys)

        if order_method:
            try:
                lead.order_method = OrderMethod(order_method)
            except ValueError:
                lead.order_method = OrderMethod.online
        if order_method_detail:
            lead.order_method_detail = order_method_detail
        if delivery_sys:
            lead.delivery_system = delivery_sys

        lead.priority = score_priority(business)

        notes_items = []
        if result.get("website_type"):
            notes_items.append(f"Type: {result.get('website_type')}")
        if result.get("technologies"):
            notes_items.append(f"Tech: {', '.join(result.get('technologies'))}")
        if result.get("delivery_providers"):
            notes_items.append(f"Delivery: {', '.join(result.get('delivery_providers'))}")
        if owner_name:
            notes_items.append(f"Owner/Manager: {owner_name}")
        if notes_items:
            lead.notes = " | ".join(notes_items)

        # Step 6: Mark Completed and Commit DB
        logger.info("[EnrichmentTask] STEP 5: DB UPDATE -> Lead.automation_status = Completed")
        lead.automation_status = AutomationStatus.completed
        lead.automation_status_detail = "Completed"

        db.commit()
        elapsed = round(time.time() - start_time, 2)
        
        # Requirement 12: Comprehensive structured log output
        logger.info("==========================================================")
        logger.info("[EnrichmentTask SUMMARY]")
        logger.info("  Lead ID: #%s (Business ID: %s)", lead.lead_ref, business.id)
        logger.info("  Website: %s (%s)", business.website, result.get("website_type", "Website"))
        logger.info("  Pages Crawled: %d", result.get("pages_crawled", 1))
        logger.info("  Emails: %s", emails)
        logger.info("  Social Profiles: %s", social)
        logger.info("  Owner/Manager: %s", owner_name or "Not Available")
        logger.info("  Technologies: %s", result.get("technologies", []))
        logger.info("  Order Method: %s (%s)", order_method, order_method_detail)
        logger.info("  Delivery System: %s", delivery_sys)
        logger.info("  Duration: %.2f seconds", elapsed)
        logger.info("  Final Status: Completed")
        logger.info("==========================================================")
        return {"status": "success", "business_id": str(business.id)}

    except Exception as exc:
        db.rollback()
        logger.exception("[EnrichmentTask] EXCEPTION processing business_id=%s: %s", business_id, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=5)
        try:
            b_uuid = uuid.UUID(business_id)
            lead = db.query(Lead).filter(Lead.business_id == b_uuid).first()
            if lead:
                lead.automation_status_detail = f"Failed ({str(exc)[:40]})"
                db.commit()
        except Exception:
            pass
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="export_leads_csv", bind=True, max_retries=3)
def export_leads_csv_task(
    self,
    city=None,
    only_unsynced=False,
    week_number=None,
    triggered_by="celery_beat",
):
    from app.services.scheduled_export import export_leads_csv

    try:
        return export_leads_csv(
            city=city,
            only_unsynced=only_unsynced,
            week_number=week_number,
            triggered_by=triggered_by,
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="export_dashboard_csv", bind=True, max_retries=3)
def export_dashboard_csv_task(self, week_number=None, triggered_by="celery_beat"):
    from app.services.scheduled_export import export_dashboard_csv

    try:
        return export_dashboard_csv(week_number=week_number, triggered_by=triggered_by)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="backfill_duplicate_businesses")
def backfill_duplicate_businesses_task():
    from app.core.database import SessionLocal
    from app.services.dedup import backfill_duplicates

    db = SessionLocal()
    try:
        return {"flagged": backfill_duplicates(db)}
    finally:
        db.close()
