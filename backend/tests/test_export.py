"""Tests for row mapping, CSV export and the Google Sheets sync."""

import csv
import io
from datetime import date

import pytest

from app.models.business import Business
from app.models.lead import AutomationStatus, CallStatus, Lead, LeadPriority, OrderMethod
from app.services.csv_export import leads_to_csv, query_leads_for_export
from app.services.export_mapping import SHEET_COLUMNS, lead_to_row
from app.services.sheets_client import DryRunSheet, _column_letter


@pytest.fixture()
def seeded_lead(db):
    """One fully-populated lead, matching a row from the team's sheet."""
    business = Business(
        name="Wai Yee Hong Chinese Supermarket",
        business_type="Asian Grocery Store",
        country="United Kingdom",
        city="Bristol",
        address="Eastgate Oriental City, Bristol",
        phone="+44 117 952 4240",
        website="waiyeehong.com",
        website_available=True,
        rating=4.6,
        reviews_count=701,
        facebook_url="facebook.com/waiyeehong",
        instagram_url="instagram.com/waiyeehong",
    )
    db.add(business)
    db.flush()

    lead = Lead(
        business_id=business.id,
        lead_ref=3,
        order_method=OrderMethod.online,
        order_method_detail="Website Orders",
        delivery_system="Own Delivery Team",
        automation_status=AutomationStatus.completed,
        priority=LeadPriority.medium,
        call_status=CallStatus.not_contacted,
        follow_up_date=date(2026, 8, 3),
        week_number=30,
        notes="Large Chinese supermarket",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


# --- row mapping -----------------------------------------------------------

def test_row_width_matches_header(seeded_lead):
    # If these ever drift apart the weekly sheet silently scrambles columns.
    assert len(lead_to_row(seeded_lead)) == len(SHEET_COLUMNS)


def test_row_values_in_sheet_order(seeded_lead):
    row = dict(zip(SHEET_COLUMNS, lead_to_row(seeded_lead)))

    assert row["Lead ID"] == "3"
    assert row["Business Name"] == "Wai Yee Hong Chinese Supermarket"
    assert row["Country"] == "United Kingdom"
    assert row["City"] == "Bristol"
    assert row["Website Available"] == "Yes"
    assert row["Google Rating"] == "4.6"
    assert row["Reviews Count"] == "701"
    assert row["Week Number"] == "30"
    assert row["Follow-up Date"] == "2026-08-03"


def test_enums_render_as_readable_text(seeded_lead):
    row = dict(zip(SHEET_COLUMNS, lead_to_row(seeded_lead)))

    # Nobody wants to read "not_contacted" in a spreadsheet.
    assert row["Automation Status"] == "Completed"
    assert row["Lead Priority"] == "Medium"
    assert row["Call Status"] == "Not Contacted"


def test_order_method_prefers_the_sheets_original_wording(seeded_lead):
    row = dict(zip(SHEET_COLUMNS, lead_to_row(seeded_lead)))
    # The enum only knows "online"; the sheet says "Website Orders".
    assert row["Order Method"] == "Website Orders"


def test_social_links_combined_into_one_cell(seeded_lead):
    row = dict(zip(SHEET_COLUMNS, lead_to_row(seeded_lead)))
    assert "facebook.com/waiyeehong" in row["Social Media Links"]
    assert "instagram.com/waiyeehong" in row["Social Media Links"]
    assert " | " in row["Social Media Links"]


def test_missing_values_render_as_not_available(db):
    business = Business(name="Bare Shop", city="Bristol")
    db.add(business)
    db.flush()
    lead = Lead(business_id=business.id, lead_ref=99)
    db.add(lead)
    db.commit()

    row = dict(zip(SHEET_COLUMNS, lead_to_row(lead)))
    assert row["Email"] == "Not Available"
    assert row["Website URL"] == "N/A"
    assert row["Website Available"] == "No"
    assert row["Social Media Links"] == "N/A"


# --- CSV -------------------------------------------------------------------

def test_csv_has_header_and_one_row_per_lead(seeded_lead, db):
    output = leads_to_csv(query_leads_for_export(db))
    rows = list(csv.reader(io.StringIO(output)))

    assert rows[0] == list(SHEET_COLUMNS)
    assert len(rows) == 2


def test_csv_quotes_commas_in_addresses(seeded_lead, db):
    output = leads_to_csv(query_leads_for_export(db))
    rows = list(csv.reader(io.StringIO(output)))

    address = rows[1][list(SHEET_COLUMNS).index("Address")]
    # Round-trips intact, so columns don't shift in Excel.
    assert address == "Eastgate Oriental City, Bristol"


def test_export_excludes_duplicates(seeded_lead, db):
    duplicate = Business(name="Dupe", city="Bristol", is_duplicate=True)
    db.add(duplicate)
    db.flush()
    db.add(Lead(business_id=duplicate.id, lead_ref=100))
    db.commit()

    assert len(query_leads_for_export(db)) == 1
    assert len(query_leads_for_export(db, include_duplicates=True)) == 2


def test_export_filters_by_city_and_priority(seeded_lead, db):
    assert len(query_leads_for_export(db, city="bristol")) == 1
    assert len(query_leads_for_export(db, city="Dubai")) == 0
    assert len(query_leads_for_export(db, priority=LeadPriority.medium)) == 1
    assert len(query_leads_for_export(db, priority=LeadPriority.high)) == 0


# --- Sheets sync -----------------------------------------------------------

def test_sync_writes_header_and_rows(seeded_lead, db, monkeypatch):
    from app.services import sheets_sync

    sheet = DryRunSheet()
    monkeypatch.setattr(sheets_sync, "open_worksheet", lambda *a, **kw: sheet)

    result = sheets_sync.sync_leads_to_sheets(db=db, triggered_by="pytest")

    assert result["status"] == "success"
    assert result["rows_written"] == 1
    assert sheet.header == list(SHEET_COLUMNS)


def test_sync_updates_instead_of_duplicating_an_existing_row(seeded_lead, db, monkeypatch):
    from app.services import sheets_sync

    # Sheet already contains Lead ID 3 at row 2 (row 1 is the header).
    sheet = DryRunSheet(existing_ids=["Lead ID", "3"])
    monkeypatch.setattr(sheets_sync, "open_worksheet", lambda *a, **kw: sheet)

    result = sheets_sync.sync_leads_to_sheets(db=db, triggered_by="pytest")

    assert result["rows_written"] == 0
    assert result["rows_updated"] == 1
    assert sheet.appended == []
    assert 2 in sheet.updated


def test_sync_is_idempotent_across_two_runs(seeded_lead, db, monkeypatch):
    """Re-running the weekly job must not duplicate rows in the sheet."""
    from app.services import sheets_sync

    written: list[list[str]] = []

    class _Recording(DryRunSheet):
        def read_column(self, col):
            # Emulate a real sheet: what was appended is there next time.
            return ["Lead ID"] + [row[0] for row in written]

        def append_rows(self, rows):
            written.extend(rows)

    sheet = _Recording()
    monkeypatch.setattr(sheets_sync, "open_worksheet", lambda *a, **kw: sheet)

    first = sheets_sync.sync_leads_to_sheets(db=db, triggered_by="pytest")
    second = sheets_sync.sync_leads_to_sheets(db=db, triggered_by="pytest")

    assert first["rows_written"] == 1
    assert second["rows_written"] == 0
    assert len(written) == 1


def test_sync_marks_leads_as_synced_and_records_a_run(seeded_lead, db, monkeypatch):
    from app.models.sync_run import SyncRun, SyncStatus
    from app.services import sheets_sync

    monkeypatch.setattr(sheets_sync, "open_worksheet", lambda *a, **kw: DryRunSheet())
    sheets_sync.sync_leads_to_sheets(db=db, triggered_by="pytest")

    db.refresh(seeded_lead)
    assert seeded_lead.synced_to_sheets is not None

    run = db.query(SyncRun).one()
    assert run.status == SyncStatus.success
    assert run.triggered_by == "pytest"
    assert run.rows_written == 1


def test_sync_records_failure_instead_of_swallowing_it(seeded_lead, db, monkeypatch):
    from app.models.sync_run import SyncRun, SyncStatus
    from app.services import sheets_sync

    def _boom(*args, **kwargs):
        raise RuntimeError("Google API quota exceeded")

    monkeypatch.setattr(sheets_sync, "open_worksheet", _boom)

    with pytest.raises(RuntimeError):
        sheets_sync.sync_leads_to_sheets(db=db, triggered_by="pytest")

    run = db.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    assert run.status == SyncStatus.failed
    assert "quota" in run.error


def test_skips_leads_with_no_lead_ref(db, monkeypatch):
    from app.services import sheets_sync

    business = Business(name="No Ref", city="Bristol")
    db.add(business)
    db.flush()
    db.add(Lead(business_id=business.id, lead_ref=None))
    db.commit()

    sheet = DryRunSheet()
    monkeypatch.setattr(sheets_sync, "open_worksheet", lambda *a, **kw: sheet)

    result = sheets_sync.sync_leads_to_sheets(db=db, triggered_by="pytest")

    # Exporting it would create a row we could never match again next run.
    assert result["rows_skipped"] == 1
    assert result["rows_written"] == 0


@pytest.mark.parametrize("index,letter", [(1, "A"), (22, "V"), (26, "Z"), (27, "AA")])
def test_column_letter(index, letter):
    assert _column_letter(index) == letter
