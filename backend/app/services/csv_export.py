"""
CSV export, using the same column mapping as the Google Sheets sync.

Exists for two reasons: it's what the frontend's "Export options" button hits
for an instant download, and it's the fallback the team can use while Google
Sheets credentials aren't set up.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.business import Business
from app.models.lead import Lead, LeadPriority
from app.services.export_mapping import SHEET_COLUMNS, lead_to_row


def query_leads_for_export(
    db: Session,
    *,
    city: Optional[str] = None,
    country: Optional[str] = None,
    priority: Optional[LeadPriority] = None,
    week_number: Optional[int] = None,
    include_duplicates: bool = False,
) -> list[Lead]:
    """Leads matching the dashboard's current filters, duplicates excluded."""
    query = (
        db.query(Lead)
        .join(Business, Lead.business_id == Business.id)
        .options(joinedload(Lead.business))
    )

    if not include_duplicates:
        query = query.filter(Business.is_duplicate.is_(False))
    if city:
        query = query.filter(Business.city.ilike(f"%{city}%"))
    if country:
        query = query.filter(Business.country.ilike(f"%{country}%"))
    if priority:
        query = query.filter(Lead.priority == priority)
    if week_number is not None:
        query = query.filter(Lead.week_number == week_number)

    return query.order_by(Lead.created_at.asc()).all()


def leads_to_csv(leads: list[Lead]) -> str:
    """Render leads as a CSV string, header included."""
    buffer = io.StringIO()
    # QUOTE_MINIMAL with \r\n: Excel's expected dialect. Notes and addresses
    # contain commas, so quoting has to be correct or columns shift.
    writer = csv.writer(buffer, lineterminator="\r\n")

    writer.writerow(SHEET_COLUMNS)
    for lead in leads:
        writer.writerow(lead_to_row(lead))

    return buffer.getvalue()


def stream_leads_csv(leads: list[Lead]) -> Iterator[str]:
    """
    Yield the CSV a row at a time, for FastAPI's StreamingResponse.

    Keeps memory flat when the team exports every lead at once instead of
    building the whole file as one string.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")

    def flush() -> str:
        value = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return value

    writer.writerow(SHEET_COLUMNS)
    yield flush()

    for lead in leads:
        writer.writerow(lead_to_row(lead))
        yield flush()


def export_filename(prefix: str = "leads") -> str:
    """Timestamped filename so repeated downloads don't overwrite each other."""
    return f"{prefix}_{datetime.utcnow():%Y%m%d_%H%M}.csv"
