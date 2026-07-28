"""
Scheduled CSV export.

Runs unattended from Celery Beat (Mondays 06:00 UTC) and writes two files into
the export directory: the full lead list, and the weekly dashboard. The team
opens them in Excel or uploads them to Google Sheets by hand.

Every run is recorded as a SyncRun row. The job fires at 6am when nobody is
watching, so without that record there's no way to tell "the file is missing
because the job failed" from "the file is missing because there were no
leads".

Files are named with the ISO week rather than a timestamp, so re-running the
same week overwrites instead of piling up near-identical files.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.lead import Lead
from app.models.sync_run import SyncRun, SyncStatus, SyncTarget
from app.services.csv_export import leads_to_csv, query_leads_for_export
from app.services.reports import build_weekly_dashboard, dashboard_to_rows

logger = logging.getLogger(__name__)


def export_directory() -> Path:
    """The folder exports are written to, created if missing."""
    directory = Path(settings.EXPORT_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _write_csv(path: Path, text: str) -> None:
    # utf-8-sig so Excel on Windows renders accented and Arabic business names
    # correctly. Without the BOM it falls back to the system codepage and
    # "Organic Foods & Café" comes out mangled.
    path.write_text(text, encoding="utf-8-sig", newline="")


def _write_rows(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        csv.writer(handle, lineterminator="\r\n").writerows(rows)


def export_leads_csv(
    *,
    city: Optional[str] = None,
    only_unsynced: bool = False,
    week_number: Optional[int] = None,
    triggered_by: str = "celery_beat",
    db: Optional[Session] = None,
) -> dict:
    """
    Write the full lead list to a CSV file.

    Args:
        city: restrict to one city, for a per-intern file.
        only_unsynced: skip leads already exported. Off by default so edits
            made since the last run still reach the file.
        week_number: names the file. Defaults to the current ISO week.
        triggered_by: recorded on the SyncRun row.
        db: session to use. One is opened and closed if omitted, which is what
            the Celery task needs — it has no request scope.
    """
    owns_session = db is None
    db = db or SessionLocal()

    dashboard_week = week_number if week_number is not None else _current_week()
    suffix = f"_{city.lower().replace(' ', '_')}" if city else ""
    filename = f"leads_week{dashboard_week:02d}{suffix}.csv"

    run = SyncRun(
        target=SyncTarget.csv,
        status=SyncStatus.running,
        triggered_by=triggered_by,
        worksheet=filename,
    )
    db.add(run)
    db.commit()

    try:
        leads = query_leads_for_export(db, city=city)
        if only_unsynced:
            leads = [lead for lead in leads if lead.exported_at is None]

        path = export_directory() / filename
        _write_csv(path, leads_to_csv(leads))

        exported_at = datetime.utcnow()
        for lead in leads:
            lead.exported_at = exported_at

        run.status = SyncStatus.success
        run.rows_written = len(leads)
        run.finished_at = exported_at
        db.commit()

        summary = {
            "status": "success",
            "file": str(path),
            "rows_written": len(leads),
            "week_number": dashboard_week,
        }
        logger.info("Lead CSV export finished: %s", summary)
        return summary

    except Exception as exc:
        # Roll back first: the failure may have left the session unusable, and
        # the SyncRun row recording what went wrong still has to be written.
        db.rollback()
        run.status = SyncStatus.failed
        run.error = f"{type(exc).__name__}: {exc}"
        run.finished_at = datetime.utcnow()
        db.add(run)
        db.commit()
        logger.exception("Lead CSV export failed")
        raise

    finally:
        if owns_session:
            db.close()


def export_dashboard_csv(
    *,
    week_number: Optional[int] = None,
    triggered_by: str = "celery_beat",
    db: Optional[Session] = None,
) -> dict:
    """Write the weekly dashboard to its own CSV file."""
    owns_session = db is None
    db = db or SessionLocal()

    week = week_number if week_number is not None else _current_week()
    filename = f"dashboard_week{week:02d}.csv"

    run = SyncRun(
        target=SyncTarget.csv,
        status=SyncStatus.running,
        triggered_by=triggered_by,
        worksheet=filename,
    )
    db.add(run)
    db.commit()

    try:
        dashboard = build_weekly_dashboard(db, week_number=week)
        rows = dashboard_to_rows(dashboard)

        path = export_directory() / filename
        _write_rows(path, rows)

        run.status = SyncStatus.success
        run.rows_written = len(rows)
        run.finished_at = datetime.utcnow()
        db.commit()

        summary = {
            "status": "success",
            "file": str(path),
            "rows_written": len(rows),
            "week_number": dashboard.week_number,
            "total_leads_this_week": dashboard.total_leads_this_week,
            "percent_of_target": dashboard.percent_of_target,
        }
        logger.info("Dashboard CSV export finished: %s", summary)
        return summary

    except Exception as exc:
        db.rollback()
        run.status = SyncStatus.failed
        run.error = f"{type(exc).__name__}: {exc}"
        run.finished_at = datetime.utcnow()
        db.add(run)
        db.commit()
        logger.exception("Dashboard CSV export failed")
        raise

    finally:
        if owns_session:
            db.close()


def run_weekly_export(*, triggered_by: str = "celery_beat") -> dict:
    """
    The Monday job: both files in one run, sharing a session.

    Returns both summaries so a failure is visible in the task result as well
    as in the SyncRun table.
    """
    db = SessionLocal()
    try:
        return {
            "leads": export_leads_csv(triggered_by=triggered_by, db=db),
            "dashboard": export_dashboard_csv(triggered_by=triggered_by, db=db),
        }
    finally:
        db.close()


def _current_week() -> int:
    from app.services.reports import current_week_number

    return current_week_number()
