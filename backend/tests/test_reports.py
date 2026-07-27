"""Tests for the Weekly Lead Generation Dashboard — app/services/reports.py."""

import pytest

from app.core.assignments import INTERNS, WEEKLY_TEAM_TARGET, intern_for_city, per_intern_target
from app.models.business import Business
from app.models.lead import Lead
from app.services.reports import build_weekly_dashboard, dashboard_to_rows

WEEK = 30


def _add_lead(db, name, city, country, business_type="Supermarket", week=WEEK, assigned_to=None):
    business = Business(
        name=name,
        city=city,
        country=country,
        business_type=business_type,
        assigned_to=assigned_to,
    )
    db.add(business)
    db.flush()
    db.add(Lead(business_id=business.id, lead_ref=None, week_number=week))
    db.commit()
    return business


# --- assignments -----------------------------------------------------------

def test_eight_interns_two_cities_each():
    assert len(INTERNS) == 8
    assert all(len(intern.cities) == 2 for intern in INTERNS)


def test_per_intern_target_rounds_up_so_team_target_is_reachable():
    # 100 / 8 = 12.5. Twelve each would leave the team 4 short every week.
    assert per_intern_target(100) == 13
    assert per_intern_target() * len(INTERNS) >= WEEKLY_TEAM_TARGET


@pytest.mark.parametrize(
    "city,expected",
    [
        ("Bristol", "Haifa"),
        ("dubai", "Haifa"),      # case-insensitive
        ("  Lahore  ", "Aiza"),  # tolerates stray whitespace
        ("Manchester", "Abdul Basit"),
        ("Atlantis", None),
    ],
)
def test_intern_for_city(city, expected):
    assert intern_for_city(city) == expected


# --- headline --------------------------------------------------------------

def test_empty_database_still_produces_a_full_dashboard(db):
    dashboard = build_weekly_dashboard(db, week_number=WEEK)

    assert dashboard.total_leads_this_week == 0
    assert dashboard.leads_still_needed == WEEKLY_TEAM_TARGET
    assert dashboard.percent_of_target == 0.0
    # Every intern must still appear — "0 leads" is the row that matters most.
    assert len(dashboard.by_intern) == 8


def test_headline_counts_only_the_requested_week(db):
    _add_lead(db, "A", "Bristol", "United Kingdom", week=WEEK)
    _add_lead(db, "B", "Bristol", "United Kingdom", week=WEEK)
    _add_lead(db, "C", "Bristol", "United Kingdom", week=WEEK - 1)

    dashboard = build_weekly_dashboard(db, week_number=WEEK)
    assert dashboard.total_leads_this_week == 2


def test_percent_of_target(db):
    for i in range(10):
        _add_lead(db, f"Shop {i}", "Bristol", "United Kingdom")

    dashboard = build_weekly_dashboard(db, week_number=WEEK, team_target=100)
    assert dashboard.percent_of_target == 10.0
    assert dashboard.leads_still_needed == 90


def test_exceeding_target_does_not_report_negative_shortfall(db):
    for i in range(5):
        _add_lead(db, f"Shop {i}", "Bristol", "United Kingdom")

    dashboard = build_weekly_dashboard(db, week_number=WEEK, team_target=3)
    assert dashboard.leads_still_needed == 0


def test_duplicates_do_not_count_towards_the_target(db):
    _add_lead(db, "Real Shop", "Bristol", "United Kingdom")

    dupe = Business(name="Dupe", city="Bristol", country="United Kingdom", is_duplicate=True)
    db.add(dupe)
    db.flush()
    db.add(Lead(business_id=dupe.id, week_number=WEEK))
    db.commit()

    # Padding the count with duplicates is exactly what this project exists
    # to stop.
    assert build_weekly_dashboard(db, week_number=WEEK).total_leads_this_week == 1


# --- by country ------------------------------------------------------------

def test_all_tracked_countries_present_even_at_zero(db):
    _add_lead(db, "A", "Bristol", "United Kingdom")

    countries = {row.country: row for row in build_weekly_dashboard(db, week_number=WEEK).by_country}

    assert countries["United Kingdom"].leads_this_week == 1
    assert countries["Saudi Arabia"].leads_this_week == 0
    assert "Pakistan" in countries


def test_country_row_separates_this_week_from_all_time(db):
    _add_lead(db, "A", "Lahore", "Pakistan", week=WEEK)
    _add_lead(db, "B", "Lahore", "Pakistan", week=WEEK - 1)

    countries = {row.country: row for row in build_weekly_dashboard(db, week_number=WEEK).by_country}
    assert countries["Pakistan"].leads_this_week == 1
    assert countries["Pakistan"].total_leads == 2


def test_untracked_country_still_appears(db):
    _add_lead(db, "A", "Toronto", "Canada")

    countries = [row.country for row in build_weekly_dashboard(db, week_number=WEEK).by_country]
    # A lead from a new market must be visible, not silently dropped.
    assert "Canada" in countries


# --- by intern -------------------------------------------------------------

def test_leads_are_attributed_by_city_when_assigned_to_is_missing(db):
    # The scraper bots know the city they searched, not who asked for it.
    _add_lead(db, "A", "Bristol", "United Kingdom", assigned_to=None)

    interns = {row.intern: row for row in build_weekly_dashboard(db, week_number=WEEK).by_intern}
    assert interns["Haifa"].leads_this_week == 1


def test_explicit_assigned_to_wins_over_city(db):
    _add_lead(db, "A", "Bristol", "United Kingdom", assigned_to="Fajar")

    interns = {row.intern: row for row in build_weekly_dashboard(db, week_number=WEEK).by_intern}
    assert interns["Fajar"].leads_this_week == 1
    assert interns["Haifa"].leads_this_week == 0


def test_on_track_flag_and_shortfall(db):
    target = per_intern_target()
    for i in range(target):
        _add_lead(db, f"Shop {i}", "Bristol", "United Kingdom")

    interns = {row.intern: row for row in build_weekly_dashboard(db, week_number=WEEK).by_intern}

    assert interns["Haifa"].on_track is True
    assert interns["Haifa"].shortfall == 0
    assert interns["Usman"].on_track is False
    assert interns["Usman"].shortfall == target


# --- by business type ------------------------------------------------------

def test_business_types_counted_all_time(db):
    _add_lead(db, "A", "Bristol", "United Kingdom", business_type="Mini Mart", week=WEEK)
    _add_lead(db, "B", "Bristol", "United Kingdom", business_type="Mini Mart", week=WEEK - 5)

    types = {row.business_type: row.total_leads for row in build_weekly_dashboard(db, week_number=WEEK).by_business_type}
    assert types["Mini Mart"] == 2
    assert types["Specialty Food Store"] == 0


def test_unlisted_business_type_appears(db):
    _add_lead(db, "A", "Leeds", "United Kingdom", business_type="Discount Supermarket")

    types = [row.business_type for row in build_weekly_dashboard(db, week_number=WEEK).by_business_type]
    assert "Discount Supermarket" in types


# --- serialisation ---------------------------------------------------------

def test_to_dict_has_the_four_sections(db):
    payload = build_weekly_dashboard(db, week_number=WEEK).to_dict()

    assert set(payload) >= {"week_number", "headline", "by_country", "by_intern", "by_business_type"}
    assert payload["headline"]["weekly_target"] == WEEKLY_TEAM_TARGET


def test_dashboard_rows_render_the_expected_layout(db):
    _add_lead(db, "A", "Bristol", "United Kingdom")

    rows = dashboard_to_rows(build_weekly_dashboard(db, week_number=WEEK))
    flat = [cell for row in rows for cell in row]

    assert "Weekly Lead Generation Dashboard" in flat
    assert "Leads by Country (this week)" in flat
    assert "Leads by Intern (this week)" in flat
    assert "Leads by Business Type (all time)" in flat
    assert "Haifa" in flat
