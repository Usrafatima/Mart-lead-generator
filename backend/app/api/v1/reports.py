"""
Reporting endpoints — the Weekly Lead Generation Dashboard.

Returns plain JSON so the Next.js dashboard can render the stat tiles and
tables directly, plus a CSV download of the same numbers laid out the way the
team's spreadsheet reads.
"""

from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.assignments import (
    INTERNS,
    TRACKED_BUSINESS_TYPES,
    TRACKED_COUNTRIES,
    WEEKLY_TEAM_TARGET,
    per_intern_target,
)
from app.core.database import get_db
from app.deps import get_current_user
from app.services.reports import (
    build_weekly_dashboard,
    current_week_number,
    dashboard_to_rows,
)

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


@router.get("/weekly/csv")
def weekly_dashboard_csv(
    week_number: Optional[int] = Query(default=None, ge=1, le=53),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Download the dashboard as a CSV, laid out the way the team's sheet reads.

    Generated inline rather than queued: it's a handful of aggregate rows, so
    there's nothing to wait for.
    """
    dashboard = build_weekly_dashboard(db, week_number=week_number)
    rows = dashboard_to_rows(dashboard)

    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\r\n").writerows(rows)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="dashboard_week{dashboard.week_number:02d}.csv"'
            )
        },
    )
