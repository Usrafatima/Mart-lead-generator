"""
Export leads from PostgreSQL to Google Sheets.

Called by the weekly Celery beat job (Mondays 06:00 UTC) and by the manual
trigger endpoint in app/api/v1/exports.py.

The export is an idempotent upsert keyed on Lead ID, not an append: the weekly
job re-running, or someone clicking Export twice, must not duplicate rows in
the sheet. A lead already present is updated in place, which also means edits
the AI service or the dashboard made since the last run get reflected.

Duplicate businesses (is_duplicate=True) are never exported.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.business import Business
from app.models.lead import Lead
from app.models.sync_run import SyncRun, SyncStatus, SyncTarget
from app.services.export_mapping import SHEET_COLUMNS, lead_to_row
from app.services.sheets_client import SheetsUnavailable, open_worksheet

logger = logging.getLogger(__name__)

# Column in the sheet holding the Lead ID, used to match existing rows.
_LEAD_ID_COLUMN = 1


def _query_leads(db: Session, *, city: Optional[str], only_unsynced: bool) -> list[Lead]:
    """
    Leads eligible for export, oldest first so Lead IDs land in order.

    joinedload avoids an N+1 query — every row needs its business, and the
    weekly run can cover hundreds of leads.
    """
    query = (
        db.query(Lead)
        .join(Business, Lead.business_id == Business.id)
        .options(joinedload(Lead.business))
        .filter(Business.is_duplicate.is_(False))
    )

    if city:
        query = query.filter(Business.city.ilike(f"%{city}%"))
    if only_unsynced:
        query = query.filter(Lead.synced_to_sheets.is_(None))

    return query.order_by(Lead.created_at.asc()).all()


def _existing_row_numbers(sheet) -> dict[str, int]:
    """
    Map Lead ID -> sheet row number for rows already in the tab.

    Row 1 is the header, so data starts at row 2.
    """
    column = sheet.read_column(_LEAD_ID_COLUMN)
    mapping: dict[str, int] = {}

    for offset, value in enumerate(column[1:], start=2):
        key = (value or "").strip()
        if key:
            mapping[key] = offset

    return mapping


def sync_leads_to_sheets(
    *,
    worksheet: Optional[str] = None,
    city: Optional[str] = None,
    only_unsynced: bool = False,
    triggered_by: str = "celery_beat",
    db: Optional[Session] = None,
) -> dict:
    """
    Push leads to the configured Google Sheet.

    Args:
        worksheet: tab name. Defaults to GOOGLE_SHEETS_WORKSHEET setting.
        city: export only this city (used for per-intern exports).
        only_unsynced: skip leads already exported. Off by default so edits
            made after the first export still reach the sheet.
        triggered_by: recorded on the SyncRun row for the audit trail.
        db: session to use. A new one is opened and closed if omitted, which
            is what the Celery task does — it has no request scope.

    Returns a summary dict, also persisted as a SyncRun row.
    """
    owns_session = db is None
    db = db or SessionLocal()

    tab = worksheet or settings.GOOGLE_SHEETS_WORKSHEET
    run = SyncRun(
        target=SyncTarget.google_sheets,
        status=SyncStatus.running,
        triggered_by=triggered_by,
        worksheet=tab,
    )
    db.add(run)
    db.commit()

    try:
        leads = _query_leads(db, city=city, only_unsynced=only_unsynced)
        logger.info("Sheets sync: %s lead(s) eligible for tab %r", len(leads), tab)

        sheet = open_worksheet(tab, len(SHEET_COLUMNS))
        sheet.ensure_header(list(SHEET_COLUMNS))

        existing = _existing_row_numbers(sheet)

        to_append: list[list[str]] = []
        appended_leads: list[Lead] = []
        updated_count = 0
        skipped = 0

        for lead in leads:
            row = lead_to_row(lead)
            lead_id = row[_LEAD_ID_COLUMN - 1].strip()

            if not lead_id:
                # No Lead ID means the sequence didn't fire (record inserted
                # outside the app). Exporting it would create a row we could
                # never match again on the next run, so skip it loudly.
                logger.warning("Skipping lead %s: no lead_ref assigned", lead.id)
                skipped += 1
                continue

            row_number = existing.get(lead_id)
            if row_number is not None:
                sheet.update_row(row_number, row)
                updated_count += 1
            else:
                to_append.append(row)
                appended_leads.append(lead)

        # Batched: one API call for all new rows instead of one per row, which
        # matters against Google's per-minute write quota.
        sheet.append_rows(to_append)

        synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
        for lead in leads:
            if lead.lead_ref is not None:
                lead.synced_to_sheets = synced_at

        run.status = SyncStatus.success
        run.rows_written = len(to_append)
        run.rows_updated = updated_count
        run.rows_skipped = skipped
        run.finished_at = datetime.utcnow()
        db.commit()

        summary = {
            "status": "success",
            "worksheet": tab,
            "rows_written": len(to_append),
            "rows_updated": updated_count,
            "rows_skipped": skipped,
            "total_considered": len(leads),
            "dry_run": type(sheet).__name__ == "DryRunSheet",
        }
        logger.info("Sheets sync finished: %s", summary)
        return summary

    except Exception as exc:
        # Roll back first: the failure may have left the session unusable, and
        # we still need to write the SyncRun row recording what went wrong.
        db.rollback()
        run.status = SyncStatus.failed
        run.error = f"{type(exc).__name__}: {exc}"
        run.finished_at = datetime.utcnow()
        db.add(run)
        db.commit()

        logger.exception("Sheets sync failed")
        if isinstance(exc, SheetsUnavailable):
            return {"status": "failed", "error": str(exc), "worksheet": tab}
        raise

    finally:
        if owns_session:
            db.close()


def sync_dashboard_to_sheets(
    *,
    worksheet: Optional[str] = None,
    week_number: Optional[int] = None,
    triggered_by: str = "celery_beat",
    db: Optional[Session] = None,
) -> dict:
    """
    Rebuild the Weekly Dashboard tab from the database.

    Unlike the leads export this replaces the whole tab rather than upserting:
    the dashboard is a snapshot of aggregates, so there's nothing to preserve
    between runs and a stale row would be misleading.
    """
    from app.services.reports import build_weekly_dashboard, dashboard_to_rows

    owns_session = db is None
    db = db or SessionLocal()

    tab = worksheet or settings.GOOGLE_SHEETS_DASHBOARD_WORKSHEET
    run = SyncRun(
        target=SyncTarget.google_sheets,
        status=SyncStatus.running,
        triggered_by=triggered_by,
        worksheet=tab,
    )
    db.add(run)
    db.commit()

    try:
        dashboard = build_weekly_dashboard(db, week_number=week_number)
        rows = dashboard_to_rows(dashboard)

        sheet = open_worksheet(tab, max(len(row) for row in rows) if rows else 5)
        sheet.replace_all(rows)

        run.status = SyncStatus.success
        run.rows_written = len(rows)
        run.finished_at = datetime.utcnow()
        db.commit()

        summary = {
            "status": "success",
            "worksheet": tab,
            "week_number": dashboard.week_number,
            "rows_written": len(rows),
            "total_leads_this_week": dashboard.total_leads_this_week,
            "percent_of_target": dashboard.percent_of_target,
            "dry_run": type(sheet).__name__ == "DryRunSheet",
        }
        logger.info("Dashboard sync finished: %s", summary)
        return summary

    except Exception as exc:
        db.rollback()
        run.status = SyncStatus.failed
        run.error = f"{type(exc).__name__}: {exc}"
        run.finished_at = datetime.utcnow()
        db.add(run)
        db.commit()

        logger.exception("Dashboard sync failed")
        if isinstance(exc, SheetsUnavailable):
            return {"status": "failed", "error": str(exc), "worksheet": tab}
        raise

    finally:
        if owns_session:
            db.close()
