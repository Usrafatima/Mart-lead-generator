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
}


@celery_app.task(name="sync_leads_to_sheets")
def sync_leads_to_sheets_task():
    """
    Placeholder hook. The actual Google Sheets export logic belongs to the
    Database & Google Sheets Integration module — this task just needs to
    call into that module's sync function once it exists, and Celery Beat
    (scheduled above) runs it weekly per the requirements.
    """
    from app.services.sheets_sync import sync_leads_to_sheets

    return sync_leads_to_sheets()
