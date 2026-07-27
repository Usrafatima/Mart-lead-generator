"""Tests for importing the team's hand-filled sheet — app/services/importer.py."""

from pathlib import Path

import pytest

from app.models.business import Business
from app.models.lead import CallStatus, Lead, LeadPriority, OrderMethod
from app.services.importer import (
    _coarse_order_method,
    _split_social,
    import_file,
    import_row,
    import_rows,
)

SAMPLE_CSV = Path(__file__).resolve().parents[1] / "data" / "sample_leads.csv"


def _row(**overrides) -> dict:
    """A raw sheet row, keyed by the team's real column headers."""
    row = {
        "Lead ID": "1",
        "Business Name": "Nihow Asian Supermarket",
        "Business Type": "Asian Grocery Store",
        "Country": "United Kingdom",
        "City": "Bristol",
        "Address": "6 Baldwin St, Bristol BS1 1SA",
        "Phone Number": "+44 7737 027926",
        "Email": "Not Available",
        "Website Available": "No",
        "Website URL": "N/A",
        "Owner/Manager Name": "Not Available",
        "Social Media Links": "N/A",
        "Order Method": "Walk-in + Delivery",
        "Delivery System": "Third-party Delivery",
        "Automation Status": "Semi Automated",
        "Google Rating": "5.0",
        "Reviews Count": "268",
        "Lead Priority": "High",
        "Notes": "On Uber Eats but no official website",
        "Call Status": "Not Contacted",
        "Follow-up Date": "N/A",
        "Week Number": "30",
    }
    row.update(overrides)
    return row


def test_imports_a_row_into_business_and_lead(db):
    lead, created = import_row(db, _row())
    db.commit()

    assert created is True
    assert lead is not None

    business = db.query(Business).one()
    assert business.name == "Nihow Asian Supermarket"
    assert business.country == "United Kingdom"
    assert business.rating == 5.0
    assert business.reviews_count == 268


def test_placeholder_text_becomes_null_not_a_literal_string(db):
    import_row(db, _row())
    db.commit()

    business = db.query(Business).one()
    # "Not Available" / "N/A" are how the team writes "empty" — storing them
    # verbatim would make every blank field look populated.
    assert business.email is None
    assert business.website is None
    assert business.owner_manager_name is None


def test_enum_columns_are_parsed_from_display_text(db):
    lead, _ = import_row(db, _row())
    db.commit()

    assert lead.priority == LeadPriority.high
    assert lead.call_status == CallStatus.not_contacted
    assert lead.week_number == 30


def test_order_method_keeps_original_text_and_coarse_enum(db):
    lead, _ = import_row(db, _row())
    db.commit()

    assert lead.order_method_detail == "Walk-in + Delivery"
    assert lead.order_method == OrderMethod.in_person


@pytest.mark.parametrize(
    "detail,expected",
    [
        ("Website Orders", OrderMethod.online),
        ("Website + Mobile", OrderMethod.online),
        ("Walk-in Only", OrderMethod.in_person),
        ("Phone Orders", OrderMethod.phone),
        (None, OrderMethod.unknown),
        ("Something else", OrderMethod.unknown),
    ],
)
def test_coarse_order_method(detail, expected):
    assert _coarse_order_method(detail) == expected


def test_unrecognised_enum_value_falls_back_without_failing(db):
    # One odd cell must not cost the whole import.
    lead, _ = import_row(db, _row(**{"Lead Priority": "Urgent!!"}))
    db.commit()
    assert lead.priority == LeadPriority.medium


def test_social_links_cell_is_split_into_columns():
    result = _split_social(
        "facebook.com/x | instagram.com/y | linkedin.com/company/z | wa.me/971501104711"
    )
    assert result["facebook_url"] == "facebook.com/x"
    assert result["instagram_url"] == "instagram.com/y"
    assert result["linkedin_url"] == "linkedin.com/company/z"
    assert result["whatsapp_number"] == "971501104711"


@pytest.mark.parametrize(
    "raw,expected_day",
    [("2026-08-03", 3), ("03/08/2026", 3), ("3 Aug 2026", 3)],
)
def test_follow_up_date_accepts_the_formats_people_actually_type(db, raw, expected_day):
    lead, _ = import_row(db, _row(**{"Follow-up Date": raw}))
    db.commit()
    assert lead.follow_up_date.day == expected_day


def test_unparseable_date_is_left_blank_rather_than_failing(db):
    lead, _ = import_row(db, _row(**{"Follow-up Date": "next tuesday"}))
    db.commit()
    assert lead.follow_up_date is None


def test_blank_business_name_row_is_skipped(db):
    lead, created = import_row(db, _row(**{"Business Name": ""}))
    assert lead is None
    assert created is False


def test_headers_are_matched_case_insensitively(db):
    lead, _ = import_row(db, {"business name": "Lower Case Shop", "CITY": "Bristol"})
    db.commit()
    assert db.query(Business).one().name == "Lower Case Shop"


def test_importing_the_same_sheet_twice_merges_instead_of_duplicating(db):
    rows = [_row(), _row(**{"Business Name": "Better Food", "Phone Number": "+44 117 946 6957"})]

    first = import_rows(db, list(rows))
    second = import_rows(db, list(rows))

    assert first["created"] == 2
    assert second["created"] == 0
    assert second["merged_as_duplicate"] == 2
    assert db.query(Business).count() == 2
    assert db.query(Lead).count() == 2


def test_assigned_to_override_tags_every_row(db):
    import_rows(db, [_row()], assigned_to="Haifa")
    assert db.query(Business).one().assigned_to == "Haifa"


@pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="sample_leads.csv not present")
def test_sample_csv_imports_cleanly(db):
    summary = import_file(db, SAMPLE_CSV, assigned_to="Haifa")

    # 15 rows from the Bristol + Dubai sheet, all distinct businesses.
    assert summary["created"] == 15
    assert summary["skipped"] == 0
    assert db.query(Business).filter(Business.city == "Bristol").count() == 8
    assert db.query(Business).filter(Business.city == "Dubai").count() == 7


@pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="sample_leads.csv not present")
def test_sample_csv_round_trips_to_export(db):
    from app.services.csv_export import leads_to_csv, query_leads_for_export

    import_file(db, SAMPLE_CSV, assigned_to="Haifa")
    output = leads_to_csv(query_leads_for_export(db))

    assert "Wai Yee Hong Chinese Supermarket" in output
    assert "Organic Foods & Café" in output


def test_rejects_unsupported_file_type(db, tmp_path):
    bad = tmp_path / "leads.txt"
    bad.write_text("nope")

    with pytest.raises(ValueError, match="Unsupported file type"):
        import_file(db, bad)


def test_missing_file_raises_clearly(db):
    with pytest.raises(FileNotFoundError):
        import_file(db, "does/not/exist.csv")
