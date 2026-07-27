from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

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

# Weekly Google Sheets export, per the "Export to Google Sheets / Schedule
# weekly jobs" requirement from the Database & Sheets module. Runs every
# Monday at 06:00 UTC. Adjust the day/hour here if the team wants a
# different schedule — no code changes needed elsewhere.
celery_app.conf.beat_schedule = {
    "weekly-sheets-sync": {
        "task": "sync_leads_to_sheets",
        "schedule": crontab(day_of_week="monday", hour=6, minute=0),
    },
    # Dashboard rebuild, 15 minutes after the leads export so it reflects the
    # rows that run just wrote. Also refreshed daily at 06:15, because a
    # progress report that's six days stale can't be acted on.
    "daily-dashboard-sync": {
        "task": "sync_dashboard_to_sheets",
        "schedule": crontab(hour=6, minute=15),
    },
}


@celery_app.task(name="sync_leads_to_sheets", bind=True, max_retries=3)
def sync_leads_to_sheets_task(
    self,
    worksheet=None,
    city=None,
    only_unsynced=False,
    triggered_by="celery_beat",
):
    """
    Run the Google Sheets export.

    Retries on failure with exponential backoff, because the usual cause is a
    transient Google API quota/timeout rather than bad data — and the next
    scheduled attempt is a week away.

    Imported inside the function so the worker doesn't pull SQLAlchemy and the
    Google client in at module import time.
    """
    from app.services.sheets_sync import sync_leads_to_sheets

    try:
        return sync_leads_to_sheets(
            worksheet=worksheet,
            city=city,
            only_unsynced=only_unsynced,
            triggered_by=triggered_by,
        )
    except Exception as exc:
        # 60s, 120s, 240s. The failure is already recorded as a SyncRun row,
        # so a permanently failing export is visible in the dashboard.
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="sync_dashboard_to_sheets", bind=True, max_retries=3)
def sync_dashboard_to_sheets_task(
    self,
    worksheet=None,
    week_number=None,
    triggered_by="celery_beat",
):
    """Rebuild the Weekly Dashboard tab in Google Sheets."""
    from app.services.sheets_sync import sync_dashboard_to_sheets

    try:
        return sync_dashboard_to_sheets(
            worksheet=worksheet,
            week_number=week_number,
            triggered_by=triggered_by,
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="backfill_duplicate_businesses")
def backfill_duplicate_businesses_task():
    """
    Re-scan every business for duplicates.

    Not scheduled — dedup happens at insert time via upsert_business(). This
    is for after a bulk import, or after the matching threshold is retuned.
    """
    from app.core.database import SessionLocal
    from app.services.dedup import backfill_duplicates

    db = SessionLocal()
    try:
        return {"flagged": backfill_duplicates(db)}
    finally:
        db.close()
