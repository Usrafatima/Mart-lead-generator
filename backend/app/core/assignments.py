"""
Who covers which cities, and the weekly lead targets.

Kept as configuration rather than a database table because it changes when
someone joins or leaves, not as part of the data flow — and because the
weekly dashboard needs to show an intern with 0 leads this week, which a
table populated from the leads themselves could never do.

Countries are listed explicitly (rather than derived from the leads) for the
same reason: "Saudi Arabia — 0 leads" is a meaningful row on the dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Team-wide goal per calendar week, from the project brief.
WEEKLY_TEAM_TARGET = 100


@dataclass(frozen=True)
class InternAssignment:
    name: str
    cities: tuple[str, ...]
    country: str


# From the assignment table: 8 interns, 2 cities each.
INTERNS: tuple[InternAssignment, ...] = (
    InternAssignment("Inza", ("London", "Dammam"), "United Kingdom"),
    InternAssignment("Abdul Basit", ("Manchester", "Leeds"), "United Kingdom"),
    InternAssignment("Fajar", ("Birmingham", "Liverpool"), "United Kingdom"),
    InternAssignment("Haifa", ("Bristol", "Dubai"), "United Kingdom"),
    InternAssignment("Fatima", ("Abu Dhabi", "Sharjah"), "United Arab Emirates"),
    InternAssignment("Usman", ("Islamabad", "Rawalpindi"), "Pakistan"),
    InternAssignment("Aiza", ("Lahore", "Faisalabad"), "Pakistan"),
    InternAssignment("Kristina", ("Karachi", "Riyadh"), "Pakistan"),
)

# Countries the dashboard always reports on, even at zero.
TRACKED_COUNTRIES: tuple[str, ...] = (
    "United Kingdom",
    "United Arab Emirates",
    "Pakistan",
    "Saudi Arabia",
)

# Business types the dashboard always reports on, in display order.
TRACKED_BUSINESS_TYPES: tuple[str, ...] = (
    "Supermarket",
    "Mini Mart",
    "Convenience Store",
    "Grocery Store",
    "Departmental Store",
    "Asian Grocery Store",
    "Local Retail Chain",
    "Organic Food Store",
    "Specialty Food Store",
)


def per_intern_target(team_target: int = WEEKLY_TEAM_TARGET) -> int:
    """
    Each intern's share of the weekly goal.

    Rounded up so the individual targets add up to at least the team target —
    100 across 8 people is 12.5, and 12 each would quietly leave the team 4
    short every week.
    """
    if not INTERNS:
        return 0
    return -(-team_target // len(INTERNS))  # ceiling division


def intern_names() -> tuple[str, ...]:
    return tuple(intern.name for intern in INTERNS)


def all_cities() -> tuple[str, ...]:
    return tuple(city for intern in INTERNS for city in intern.cities)


def intern_for_city(city: Optional[str]) -> Optional[str]:
    """
    Which intern owns a city, case-insensitively.

    Used to attribute leads that arrived without an `assigned_to` — the
    scraper bots don't set one, they only know the city they searched.
    """
    if not city:
        return None

    needle = city.strip().lower()
    for intern in INTERNS:
        if any(needle == owned.lower() for owned in intern.cities):
            return intern.name
    return None
