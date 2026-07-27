"""
Reporting endpoints — the Weekly Lead Generation Dashboard.

Returns plain JSON so the Next.js dashboard can render the stat tiles and
tables directly, and so the same numbers can be pushed to the Google Sheets
dashboard tab without computing them twice.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.assignments import (
    INTERNS,
    TRACKED_BUSINESS_TYPES,
    TRACKED_COUNTRIES,
    WEEKLY_TEAM_TARGET,
    per_intern_target,
)
from app.core.database import get_db
from app.deps import get_current_user, require_owner
from app.services.reports import build_weekly_dashboard, current_week_number

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/weekly")
def weekly_dashboard(
    week_number: Optional[int] = Query(
        default=None,
        ge=1,
        le=53,
        description="ISO week number. Defaults to the current week.",
    ),
    team_target: int = Query(default=WEEKLY_TEAM_TARGET, ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    The full dashboard: headline totals, by country, by intern, by type.

    Every tracked intern, country and business type is present even at zero —
    an intern with no leads is the row a progress report most needs to show.
    """
    dashboard = build_weekly_dashboard(db, week_number=week_number, team_target=team_target)
    return dashboard.to_dict()


@router.get("/weekly/interns")
def intern_progress(
    week_number: Optional[int] = Query(default=None, ge=1, le=53),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Just the per-intern table, for a compact progress widget."""
    dashboard = build_weekly_dashboard(db, week_number=week_number)
    return {
        "week_number": dashboard.week_number,
        "target_per_week": per_intern_target(),
        "interns": [
            {**vars(row), "shortfall": row.shortfall} for row in dashboard.by_intern
        ],
    }


@router.get("/assignments")
def assignments(current_user=Depends(get_current_user)):
    """
    Who covers which cities, and the targets.

    Configuration rather than data, but the frontend needs it to render the
    assignment table and to offer city filters.
    """
    return {
        "weekly_team_target": WEEKLY_TEAM_TARGET,
        "target_per_intern": per_intern_target(),
        "current_week": current_week_number(),
        "interns": [
            {"name": intern.name, "cities": list(intern.cities), "country": intern.country}
            for intern in INTERNS
        ],
        "tracked_countries": list(TRACKED_COUNTRIES),
        "tracked_business_types": list(TRACKED_BUSINESS_TYPES),
    }


@router.post("/weekly/sync-to-sheets")
def push_dashboard_to_sheets(
    week_number: Optional[int] = Query(default=None, ge=1, le=53),
    worksheet: Optional[str] = None,
    current_user=Depends(require_owner),
):
    """
    Rebuild the Google Sheets dashboard tab now.

    Owner-only, and queued through Celery for the same reason as the leads
    export — it's a network round trip to Google, not something to block an
    HTTP request on.
    """
    from app.workers.celery_worker import sync_dashboard_to_sheets_task

    try:
        task = sync_dashboard_to_sheets_task.delay(
            worksheet=worksheet,
            week_number=week_number,
            triggered_by=current_user.email,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not queue dashboard sync (is Redis running?): {exc}",
        ) from exc

    return {"task_id": task.id, "queued": True, "detail": "Dashboard sync queued."}
