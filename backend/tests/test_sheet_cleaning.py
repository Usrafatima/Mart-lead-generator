"""
Regression tests for the mess found in real hand-maintained lead sheets.

Each case here comes from an actual sheet the team produced. The sheets
themselves aren't in the repo — they were one-off migration data, and the
system generates its own leads now — but every parsing failure they exposed
is pinned down below so it can't come back.
"""

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
    import_rows,
)

# Header set the team used, so alias resolution is exercised as written.
HEADERS = [
    "Lead ID", "Business Name", "Business Type", "Country", "City", "Address",
    "Phone Number", "Email", "Website Available", "Website URL",
    "Owner/Manager Name", "Social Media Links", "Order Method",
    "Delivery System", "Automation Status", "Google Rating", "Reviews Count",
    "Lead Priority", "Notes", "Call Status", "Follow-up Date", "Week Number",
]


def row(**overrides) -> dict:
    base = dict.fromkeys(HEADERS, "")
    base.update(
        {
            "Lead ID": "1",
            "Business Name": "Test Shop",
            "Business Type": "Supermarket",
            "Country": "United Kingdom",
            "City": "Bristol",
            "Phone Number": "+44 117 952 4240",
            "Automation Status": "Manual",
            "Lead Priority": "High",
            "Call Status": "Not Contacted",
            "Week Number": "30",
        }
    )
    base.update(overrides)
    return base


# --- week number: written four different ways across the sheets ------------

@pytest.mark.parametrize(
    "raw,expected",
    [("30", 30), ("52", 52), ("Week 1", 1), ("week1", 1), ("Week1", 1),
     ("", None), ("N/A", None), ("99", None)],
)
def test_week_number_parsing(raw, expected):
    assert _to_week_number(raw) == expected


# --- review counts written as approximations -------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [("120+", 120), ("800+", 800), ("12000+", 12000), ("2,409", 2409),
     ("50520", 50520), ("N/A", None), ("nan", None)],
)
def test_reviews_count_parsing(raw, expected):
    assert _to_int(raw) == expected


# --- phone numbers Excel destroyed -----------------------------------------

@pytest.mark.parametrize("raw", ["4.41317E+11", "4.42085E+11", "4.42E+11"])
def test_excel_mangled_phones_are_rejected_not_guessed(raw):
    # The digits are gone permanently. A wrong number looks callable and lets
    # dedup match two unrelated shops, so blank is the only safe answer.
    assert _to_phone(raw) is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+44 20 7946 0958", "+44 20 7946 0958"),
        ("44 161 224 3441", "44 161 224 3441"),
        ("042-111-933-933", "042-111-933-933"),
        ("Not listed", None),
        ("Available on website", None),
        ("unkown", None),        # recurring typo
        ("To Verify", None),
    ],
)
def test_phone_cleaning(raw, expected):
    assert _to_phone(raw) == expected


# --- statuses written as prose ---------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Not Contacted", CallStatus.not_contacted),
        ("Not Called", CallStatus.not_contacted),
        ("Contacted – Interested", CallStatus.interested),   # en dash
        ("Contacted - Interested", CallStatus.interested),   # hyphen
        ("Attempted – No Answer", CallStatus.no_answer),
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


# --- whole-row behaviour ---------------------------------------------------

PLACEHOLDERS = [
    "nan", "N/A", "Not Available", "To Verify", "unknown", "unkown",
    "not found", "—", "Not listed", "TBD",
]


@pytest.mark.parametrize("placeholder", PLACEHOLDERS)
def test_placeholders_never_reach_the_database(db, placeholder):
    import_rows(
        db,
        [row(**{"Email": placeholder, "Website URL": placeholder,
                "Owner/Manager Name": placeholder})],
    )

    business = db.query(Business).one()
    assert business.email is None
    assert business.website is None
    assert business.owner_manager_name is None


def test_a_sheet_full_of_mess_imports_without_failing(db, sheet_csv):
    """One bad cell must not cost the whole file."""
    path = sheet_csv(
        row(**{"Business Name": "Good Shop", "Phone Number": "+44 117 952 4240"}),
        row(**{"Business Name": "Mangled Phone", "Phone Number": "4.41317E+11",
               "City": "Leeds", "Reviews Count": "120+", "Week Number": "Week 1"}),
        row(**{"Business Name": "Odd Status", "Phone Number": "+44 113 246 0388",
               "City": "Leeds", "Automation Status": "Manual (likely)",
               "Call Status": "Attempted – No Answer", "Lead Priority": "Urgent!!"}),
        row(**{"Business Name": "", "City": "Leeds"}),  # trailing blank line
    )

    summary = import_file(db, path, assigned_to="Haifa")

    assert summary["created"] == 3
    assert summary["skipped"] == 1

    mangled = db.query(Business).filter(Business.name == "Mangled Phone").one()
    assert mangled.phone is None
    assert mangled.reviews_count == 120

    odd = db.query(Lead).join(Business).filter(Business.name == "Odd Status").one()
    assert odd.call_status == CallStatus.no_answer
    assert odd.automation_status == AutomationStatus.not_started


def test_the_shared_template_row_collapses_across_sheets(db, sheet_csv):
    """
    Every intern's sheet opened with the same "ABC Mart" example row.
    Imported naively that inflates the lead count by one per sheet.
    """
    template = row(
        **{
            "Business Name": "ABC Mart",
            "City": "London",
            "Phone Number": "+44 20 7946 0958",
            "Email": "info@abcmart.co.uk",
            "Owner/Manager Name": "Ahmed Khan",
        }
    )

    for intern in ("Inza", "Abdul Basit", "Usman", "Aiza"):
        path = sheet_csv(template, name=f"{intern}.csv")
        import_file(db, path, assigned_to=intern)

    assert db.query(Business).filter(Business.name == "ABC Mart").count() == 1

    survivor = db.query(Business).one()
    assert survivor.email == "info@abcmart.co.uk"
    assert survivor.owner_manager_name == "Ahmed Khan"
    assert db.query(Lead).count() == 1


def test_reimporting_the_same_sheet_creates_nothing_new(db, sheet_csv):
    path = sheet_csv(
        row(**{"Business Name": "Shop One", "Phone Number": "+44 117 952 4240"}),
        row(**{"Business Name": "Shop Two", "Phone Number": "+44 117 946 6957"}),
    )

    first = import_file(db, path, assigned_to="Haifa")
    second = import_file(db, path, assigned_to="Haifa")

    assert first["created"] == 2
    assert second["created"] == 0
    assert second["merged_as_duplicate"] == 2
    assert db.query(Business).count() == 2


def test_week_numbers_normalise_across_differently_formatted_sheets(db, sheet_csv):
    path = sheet_csv(
        row(**{"Business Name": "A", "Week Number": "30", "Phone Number": "+44 117 952 4240"}),
        row(**{"Business Name": "B", "Week Number": "Week 1", "Phone Number": "+44 117 946 6957"}),
        row(**{"Business Name": "C", "Week Number": "week1", "Phone Number": "+44 117 973 1444"}),
        row(**{"Business Name": "D", "Week Number": "52", "Phone Number": "+44 117 929 7269"}),
    )
    import_file(db, path, assigned_to="Haifa")

    weeks = sorted(lead.week_number for lead in db.query(Lead).all())
    assert weeks == [1, 1, 30, 52]


def test_dashboard_builds_from_imported_sheet_data(db, sheet_csv):
    from app.services.reports import build_weekly_dashboard

    path = sheet_csv(
        row(**{"Business Name": "UK Shop", "Country": "United Kingdom",
               "City": "Bristol", "Phone Number": "+44 117 952 4240"}),
        row(**{"Business Name": "PK Shop", "Country": "Pakistan",
               "City": "Lahore", "Phone Number": "+92 42 111 2233"}),
    )
    import_file(db, path)

    dashboard = build_weekly_dashboard(db, week_number=30)
    countries = {r.country: r.total_leads for r in dashboard.by_country}

    assert countries["United Kingdom"] == 1
    assert countries["Pakistan"] == 1
    # Tracked but empty, so a zero is visible as a zero.
    assert countries["Saudi Arabia"] == 0
    assert len(dashboard.by_intern) == 8
