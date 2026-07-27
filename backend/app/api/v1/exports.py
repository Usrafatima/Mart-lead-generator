"""
Export endpoints — what the dashboard's "Export options" buttons call.

The Google Sheets sync is queued through Celery rather than run inline: a full
export can take a minute against Google's API and would otherwise hold the
HTTP request open until the browser times out.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user, require_owner
from app.models.lead import LeadPriority
from app.models.sync_run import SyncRun, SyncStatus, SyncTarget
from app.services.csv_export import (
    export_filename,
    query_leads_for_export,
    stream_leads_csv,
)

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


class SyncRunOut(BaseModel):
    id: uuid.UUID
    target: SyncTarget
    status: SyncStatus
    triggered_by: Optional[str] = None
    worksheet: Optional[str] = None
    rows_written: int
    rows_updated: int
    rows_skipped: int
    error: Optional[str] = None
    started_at: object
    finished_at: Optional[object] = None

    class Config:
        from_attributes = True


class SheetsSyncQueued(BaseModel):
    task_id: Optional[str] = None
    queued: bool
    detail: str


@router.get("/csv")
def export_csv(
    city: Optional[str] = None,
    country: Optional[str] = None,
    priority: Optional[LeadPriority] = None,
    week_number: Optional[int] = None,
    include_duplicates: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Download the current lead set as a CSV, using the dashboard's filters."""
    leads = query_leads_for_export(
        db,
        city=city,
        country=country,
        priority=priority,
        week_number=week_number,
        include_duplicates=include_duplicates,
    )

    filename = export_filename("leads" if not city else f"leads_{city.lower()}")

    return StreamingResponse(
        stream_leads_csv(leads),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/sheets", response_model=SheetsSyncQueued)
def trigger_sheets_sync(
    worksheet: Optional[str] = None,
    city: Optional[str] = None,
    only_unsynced: bool = False,
    current_user=Depends(require_owner),
):
    """
    Queue a Google Sheets export now, instead of waiting for Monday's job.

    Owner-only: it writes to a shared spreadsheet the whole team reads.
    """
    from app.workers.celery_worker import sync_leads_to_sheets_task

    try:
        task = sync_leads_to_sheets_task.delay(
            worksheet=worksheet,
            city=city,
            only_unsynced=only_unsynced,
            triggered_by=current_user.email,
        )
    except Exception as exc:
        # Almost always Redis being down. A 503 tells the frontend to show
        # "try again", which is accurate — the export itself is fine.
        raise HTTPException(
            status_code=503,
            detail=f"Could not queue export (is Redis running?): {exc}",
        ) from exc

    return SheetsSyncQueued(
        task_id=task.id,
        queued=True,
        detail="Export queued. Check GET /api/v1/exports/runs for the result.",
    )


@router.get("/runs", response_model=List[SyncRunOut])
def list_sync_runs(
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    History of export attempts, newest first.

    This is how you tell whether Monday's unattended job actually ran.
    """
    return db.query(SyncRun).order_by(SyncRun.started_at.desc()).limit(limit).all()
