"""Tests for row mapping, CSV export, and the scheduled export job."""

import csv
import io
from datetime import date

import pytest

from app.models.business import Business
from app.models.lead import AutomationStatus, CallStatus, Lead, LeadPriority, OrderMethod
from app.models.sync_run import SyncRun, SyncStatus, SyncTarget
from app.services.csv_export import leads_to_csv, query_leads_for_export
from app.services.export_mapping import SHEET_COLUMNS, lead_to_row


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



# --- scheduled export job --------------------------------------------------

@pytest.fixture()
def export_dir(tmp_path, monkeypatch):
    """Point the export directory at a throwaway folder for the test."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "EXPORT_DIR", str(tmp_path / "exports"))
    return tmp_path / "exports"


def test_weekly_job_writes_a_lead_file(seeded_lead, db, export_dir):
    from app.services.scheduled_export import export_leads_csv

    result = export_leads_csv(db=db, week_number=30, triggered_by="pytest")

    assert result["status"] == "success"
    assert result["rows_written"] == 1

    path = export_dir / "leads_week30.csv"
    assert path.exists()

    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    assert rows[0] == list(SHEET_COLUMNS)
    assert rows[1][1] == "Wai Yee Hong Chinese Supermarket"


def test_lead_file_is_named_by_week_so_reruns_overwrite(seeded_lead, db, export_dir):
    from app.services.scheduled_export import export_leads_csv

    export_leads_csv(db=db, week_number=30, triggered_by="pytest")
    export_leads_csv(db=db, week_number=30, triggered_by="pytest")

    # Two runs of the same week must not leave two near-identical files.
    assert [p.name for p in sorted(export_dir.glob("leads_week*.csv"))] == ["leads_week30.csv"]


def test_city_filter_gets_its_own_file(seeded_lead, db, export_dir):
    from app.services.scheduled_export import export_leads_csv

    result = export_leads_csv(db=db, week_number=30, city="Bristol", triggered_by="pytest")

    assert (export_dir / "leads_week30_bristol.csv").exists()
    assert result["rows_written"] == 1


def test_export_stamps_leads_and_records_a_run(seeded_lead, db, export_dir):
    from app.services.scheduled_export import export_leads_csv

    export_leads_csv(db=db, week_number=30, triggered_by="pytest")

    db.refresh(seeded_lead)
    assert seeded_lead.exported_at is not None

    run = db.query(SyncRun).one()
    assert run.status == SyncStatus.success
    assert run.target == SyncTarget.csv
    assert run.triggered_by == "pytest"
    assert run.rows_written == 1
    assert run.worksheet == "leads_week30.csv"


def test_only_unsynced_skips_already_exported_leads(seeded_lead, db, export_dir):
    from app.services.scheduled_export import export_leads_csv

    export_leads_csv(db=db, week_number=30, triggered_by="pytest")
    second = export_leads_csv(db=db, week_number=30, only_unsynced=True, triggered_by="pytest")

    assert second["rows_written"] == 0


def test_failure_is_recorded_instead_of_swallowed(seeded_lead, db, export_dir, monkeypatch):
    from app.services import scheduled_export

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(scheduled_export, "_write_csv", _boom)

    with pytest.raises(OSError):
        scheduled_export.export_leads_csv(db=db, week_number=30, triggered_by="pytest")

    # The 06:00 Monday job runs unattended; a silent failure would look
    # identical to a week with no leads.
    run = db.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    assert run.status == SyncStatus.failed
    assert "disk full" in run.error


def test_dashboard_file_is_written(seeded_lead, db, export_dir):
    from app.services.scheduled_export import export_dashboard_csv

    result = export_dashboard_csv(db=db, week_number=30, triggered_by="pytest")

    assert result["status"] == "success"
    assert result["total_leads_this_week"] == 1

    path = export_dir / "dashboard_week30.csv"
    assert path.exists()

    text = path.read_text(encoding="utf-8-sig")
    assert "Weekly Lead Generation Dashboard" in text
    assert "Leads by Intern (this week)" in text
    assert "Haifa" in text


def test_weekly_run_produces_both_files(seeded_lead, db, export_dir, monkeypatch):
    from app.services import scheduled_export

    # run_weekly_export opens its own session; point it at the test's.
    monkeypatch.setattr(scheduled_export, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    result = scheduled_export.run_weekly_export(triggered_by="pytest")

    assert result["leads"]["status"] == "success"
    assert result["dashboard"]["status"] == "success"
    assert len(list(export_dir.glob("*.csv"))) == 2


def test_export_directory_is_created_if_missing(db, export_dir):
    from app.services.scheduled_export import export_directory

    assert not export_dir.exists()
    assert export_directory() == export_dir
    assert export_dir.exists()


def test_files_are_written_with_a_bom_for_excel(seeded_lead, db, export_dir):
    from app.services.scheduled_export import export_leads_csv

    export_leads_csv(db=db, week_number=30, triggered_by="pytest")

    raw = (export_dir / "leads_week30.csv").read_bytes()
    # Without the BOM, Excel on Windows falls back to the system codepage and
    # mangles accented and Arabic business names.
    assert raw.startswith(b"\xef\xbb\xbf")
