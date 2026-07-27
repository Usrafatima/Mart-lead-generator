"""
Weekly Lead Generation Dashboard.

Reproduces the dashboard the team was maintaining with spreadsheet formulas
(WEEKNUM + COUNTIFS), but computed from the database instead. The formula
version showed `#VALUE!` for every intern because it depended on a column
being typed consistently by eight different people — the whole reason this
project moved off Excel.

Four sections, matching the agreed layout:
  1. headline  — this week's total vs target
  2. by_country
  3. by_intern — including interns who logged nothing this week
  4. by_business_type (all time)

Rows are always present for every tracked intern/country/type, at zero if
there's no data. A dashboard that silently omits the person with no leads is
worse than useless for a progress report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.assignments import (
    INTERNS,
    TRACKED_BUSINESS_TYPES,
    TRACKED_COUNTRIES,
    WEEKLY_TEAM_TARGET,
    intern_for_city,
    per_intern_target,
)
from app.models.business import Business
from app.models.lead import Lead


def current_week_number(today: Optional[date] = None) -> int:
    """ISO week number, the same basis as the sheet's WEEKNUM column."""
    return (today or date.today()).isocalendar().week


@dataclass
class CountryRow:
    country: str
    leads_this_week: int
    total_leads: int


@dataclass
class InternRow:
    intern: str
    cities: list[str]
    leads_this_week: int
    target_per_week: int
    on_track: bool

    @property
    def shortfall(self) -> int:
        return max(self.target_per_week - self.leads_this_week, 0)


@dataclass
class BusinessTypeRow:
    business_type: str
    total_leads: int


@dataclass
class WeeklyDashboard:
    week_number: int
    generated_at: datetime

    total_leads_this_week: int
    weekly_target: int
    leads_still_needed: int

    by_country: list[CountryRow] = field(default_factory=list)
    by_intern: list[InternRow] = field(default_factory=list)
    by_business_type: list[BusinessTypeRow] = field(default_factory=list)

    @property
    def percent_of_target(self) -> float:
        if self.weekly_target <= 0:
            return 0.0
        return round(self.total_leads_this_week / self.weekly_target * 100, 1)

    def to_dict(self) -> dict:
        return {
            "week_number": self.week_number,
            "generated_at": self.generated_at.isoformat(),
            "headline": {
                "total_leads_this_week": self.total_leads_this_week,
                "weekly_target": self.weekly_target,
                "percent_of_target": self.percent_of_target,
                "leads_still_needed": self.leads_still_needed,
            },
            "by_country": [vars(row) for row in self.by_country],
            "by_intern": [
                {**vars(row), "shortfall": row.shortfall} for row in self.by_intern
            ],
            "by_business_type": [vars(row) for row in self.by_business_type],
        }


def _base_query(db: Session):
    """Leads joined to their business, duplicates excluded.

    Duplicates must not count towards anyone's weekly target — that's exactly
    the padding this project exists to stop.
    """
    return (
        db.query(Lead, Business)
        .join(Business, Lead.business_id == Business.id)
        .filter(Business.is_duplicate.is_(False))
    )


def _attributed_intern(business: Business) -> Optional[str]:
    """
    Who gets credit for a lead.

    Prefers the explicit `assigned_to` set at import; falls back to the city's
    owner, since the scraper bots know the city they searched but not who
    asked for it.
    """
    return business.assigned_to or intern_for_city(business.city)


def build_weekly_dashboard(
    db: Session,
    *,
    week_number: Optional[int] = None,
    team_target: int = WEEKLY_TEAM_TARGET,
) -> WeeklyDashboard:
    """Assemble the dashboard for a given ISO week (defaults to the current one)."""
    week = week_number if week_number is not None else current_week_number()

    rows = _base_query(db).all()
    this_week = [(lead, business) for lead, business in rows if lead.week_number == week]

    total_this_week = len(this_week)

    # --- by country --------------------------------------------------------
    week_by_country: dict[str, int] = {}
    all_by_country: dict[str, int] = {}
    for lead, business in rows:
        country = (business.country or "Unspecified").strip()
        all_by_country[country] = all_by_country.get(country, 0) + 1
        if lead.week_number == week:
            week_by_country[country] = week_by_country.get(country, 0) + 1

    countries = list(TRACKED_COUNTRIES)
    # Include anything in the data that isn't on the tracked list, so a lead
    # from a new country is visible rather than silently dropped.
    countries += sorted(c for c in all_by_country if c not in countries)

    by_country = [
        CountryRow(
            country=country,
            leads_this_week=week_by_country.get(country, 0),
            total_leads=all_by_country.get(country, 0),
        )
        for country in countries
    ]

    # --- by intern ---------------------------------------------------------
    week_by_intern: dict[str, int] = {}
    for lead, business in this_week:
        intern = _attributed_intern(business)
        if intern:
            week_by_intern[intern] = week_by_intern.get(intern, 0) + 1

    target = per_intern_target(team_target)
    by_intern = [
        InternRow(
            intern=intern.name,
            cities=list(intern.cities),
            leads_this_week=week_by_intern.get(intern.name, 0),
            target_per_week=target,
            on_track=week_by_intern.get(intern.name, 0) >= target,
        )
        for intern in INTERNS
    ]

    # --- by business type (all time) --------------------------------------
    type_counts: dict[str, int] = {}
    for _lead, business in rows:
        label = (business.business_type or "Unspecified").strip()
        type_counts[label] = type_counts.get(label, 0) + 1

    types = list(TRACKED_BUSINESS_TYPES)
    types += sorted(t for t in type_counts if t not in types)

    by_business_type = [
        BusinessTypeRow(business_type=label, total_leads=type_counts.get(label, 0))
        for label in types
    ]

    return WeeklyDashboard(
        week_number=week,
        generated_at=datetime.utcnow(),
        total_leads_this_week=total_this_week,
        weekly_target=team_target,
        leads_still_needed=max(team_target - total_this_week, 0),
        by_country=by_country,
        by_intern=by_intern,
        by_business_type=by_business_type,
    )


def dashboard_to_rows(dashboard: WeeklyDashboard) -> list[list[str]]:
    """
    Flatten the dashboard into spreadsheet rows for the Google Sheets tab.

    Deliberately mirrors the layout the team already reads, section headers
    and blank spacer rows included, so the generated tab is recognisable.
    """
    percent = f"{dashboard.percent_of_target:g}%"

    rows: list[list[str]] = [
        ["Weekly Lead Generation Dashboard"],
        [f"Week {dashboard.week_number} — generated {dashboard.generated_at:%Y-%m-%d %H:%M} UTC"],
        [],
        ["This Week's Total Leads", "Weekly Target", "% of Target Reached", "Leads Still Needed"],
        [
            str(dashboard.total_leads_this_week),
            str(dashboard.weekly_target),
            percent,
            str(dashboard.leads_still_needed),
        ],
        [],
        ["Leads by Country (this week)"],
        ["Country", "Leads This Week", "Total Leads (all time)"],
    ]

    rows += [
        [row.country, str(row.leads_this_week), str(row.total_leads)]
        for row in dashboard.by_country
    ]

    rows += [
        [],
        ["Leads by Intern (this week)"],
        ["Intern", "Cities", "Leads This Week", "Target/Week", "On Track?"],
    ]
    rows += [
        [
            row.intern,
            " + ".join(row.cities),
            str(row.leads_this_week),
            str(row.target_per_week),
            "Yes" if row.on_track else "No",
        ]
        for row in dashboard.by_intern
    ]

    rows += [
        [],
        ["Leads by Business Type (all time)"],
        ["Business Type", "Total Leads"],
    ]
    rows += [
        [row.business_type, str(row.total_leads)] for row in dashboard.by_business_type
    ]

    return rows
