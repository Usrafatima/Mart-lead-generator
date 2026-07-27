"""
Import tests against the interns' actual sheets.

These files are the real thing, mess included: pandas "nan", Excel-mangled
phone numbers, "To Verify" placeholders, four different spellings of the week
column. Every failure here is a bug that would otherwise land in the database.
"""

from pathlib import Path

import pytest

from app.models.business import Business
from app.models.lead import AutomationStatus, CallStatus, Lead
from app.services.importer import (
    _coarse_automation_status,
    _to_call_status,
    _to_int,
    _to_phone,
    _to_week_number,
    import_file,
)

DATA = Path(__file__).resolve().parents[1] / "data"

SHEETS = {
    "Haifa": DATA / "sample_leads.csv",
    "Inza": DATA / "leads_inza_london_dammam.csv",
    "Abdul Basit": DATA / "leads_abdulbasit_manchester_leeds.csv",
    "Usman": DATA / "leads_usman_islamabad_rawalpindi.csv",
    "Aiza": DATA / "leads_aiza_lahore_faisalabad.csv",
}


# --- the individual cleaners ----------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("30", 30),
        ("52", 52),
        ("Week 1", 1),
        ("week1", 1),
        ("Week1", 1),
        ("", None),
        ("N/A", None),
        ("99", None),   # out of range 1-53, rejected rather than stored
    ],
)
def test_week_number_parsing(raw, expected):
    assert _to_week_number(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [("120+", 120), ("800+", 800), ("2,409", 2409), ("50520", 50520), ("N/A", None), ("nan", None)],
)
def test_reviews_count_parsing(raw, expected):
    assert _to_int(raw) == expected


@pytest.mark.parametrize("raw", ["4.41317E+11", "4.42085E+11", "4.42E+11"])
def test_excel_mangled_phones_are_rejected_not_guessed(raw):
    # These have lost digits permanently. A wrong number looks callable and
    # would let dedup match two unrelated shops, so blank is the safe answer.
    assert _to_phone(raw) is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+44 20 7946 0958", "+44 20 7946 0958"),
        ("44 161 224 3441", "44 161 224 3441"),
        ("042-111-933-933", "042-111-933-933"),
        ("Not listed", None),
        ("Available on website", None),
        ("unkown", None),
    ],
)
def test_phone_cleaning(raw, expected):
    assert _to_phone(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Not Contacted", CallStatus.not_contacted),
        ("Not Called", CallStatus.not_contacted),
        ("Contacted – Interested", CallStatus.interested),   # en dash
        ("Contacted - Interested", CallStatus.interested),   # hyphen
        ("", CallStatus.not_contacted),
    ],
)
def test_call_status_parsing(raw, expected):
    assert _to_call_status(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Manual", AutomationStatus.not_started),
        ("Manual (likely)", AutomationStatus.not_started),
        ("Semi Automated", AutomationStatus.in_progress),
        ("Semi-Automated?", AutomationStatus.in_progress),
        ("Automated", AutomationStatus.completed),
        ("Fully Automated", AutomationStatus.completed),
    ],
)
def test_automation_status_parsing(raw, expected):
    assert _coarse_automation_status(raw) == expected


# --- whole-file imports ----------------------------------------------------

@pytest.mark.parametrize("intern,path", SHEETS.items(), ids=list(SHEETS))
def test_each_sheet_imports_without_error(db, intern, path):
    if not path.exists():
        pytest.skip(f"{path.name} not present")

    summary = import_file(db, path, assigned_to=intern)
    assert summary["created"] > 0
    assert summary["skipped"] == 0


def test_placeholders_never_reach_the_database(db):
    for intern, path in SHEETS.items():
        if path.exists():
            import_file(db, path, assigned_to=intern)

    junk = {"nan", "n/a", "N/A", "Not Available", "To Verify", "unknown", "unkown", "not found", "—"}

    for business in db.query(Business).all():
        for field in ("email", "website", "owner_manager_name", "phone", "business_type"):
            value = getattr(business, field)
            assert value not in junk, f"{business.name}.{field} stored placeholder {value!r}"


def test_the_shared_template_row_collapses_to_one_lead(db):
    """
    Every intern's sheet starts with the same "ABC Mart" London example row.
    Imported naively that's five identical leads inflating the count.
    """
    present = [(i, p) for i, p in SHEETS.items() if p.exists()]
    if len(present) < 2:
        pytest.skip("need at least two sheets to test cross-intern dedup")

    for intern, path in present:
        import_file(db, path, assigned_to=intern)

    abc = db.query(Business).filter(
        Business.name.ilike("%ABC Mart%"),
        Business.is_duplicate.is_(False),
    ).all()

    assert len(abc) == 1, f"ABC Mart should collapse to one lead, got {len(abc)}"

    # Merged on the way in, so the repeats were never written at all — there
    # is exactly one ABC Mart row in the table, flagged or not.
    assert db.query(Business).filter(Business.name.ilike("%ABC Mart%")).count() == 1

    # And it kept the detail from the sheets, rather than being a bare stub.
    assert abc[0].email == "info@abcmart.co.uk"
    assert abc[0].owner_manager_name == "Ahmed Khan"

    # One lead, not five.
    assert db.query(Lead).filter(Lead.business_id == abc[0].id).count() == 1


def test_reimporting_every_sheet_creates_nothing_new(db):
    present = [(i, p) for i, p in SHEETS.items() if p.exists()]
    if not present:
        pytest.skip("no sheets present")

    for intern, path in present:
        import_file(db, path, assigned_to=intern)
    count_after_first = db.query(Business).count()

    for intern, path in present:
        summary = import_file(db, path, assigned_to=intern)
        assert summary["created"] == 0

    assert db.query(Business).count() == count_after_first


def test_week_numbers_are_normalised_across_sheets(db):
    for intern, path in SHEETS.items():
        if path.exists():
            import_file(db, path, assigned_to=intern)

    weeks = {lead.week_number for lead in db.query(Lead).all() if lead.week_number is not None}
    # "Week 1", "week1", "52" and "30" all become plain integers in range.
    assert weeks
    assert all(1 <= week <= 53 for week in weeks)


def test_dashboard_builds_from_the_real_data(db):
    from app.services.reports import build_weekly_dashboard

    for intern, path in SHEETS.items():
        if path.exists():
            import_file(db, path, assigned_to=intern)

    dashboard = build_weekly_dashboard(db, week_number=52)

    assert len(dashboard.by_intern) == 8
    countries = {row.country: row.total_leads for row in dashboard.by_country}
    assert countries["Pakistan"] > 0
    assert countries["United Kingdom"] > 0
    # Never reported on but always shown, so a zero is visible as a zero.
    assert countries["Saudi Arabia"] == 0
