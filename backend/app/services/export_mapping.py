"""
The single definition of what a lead looks like as a spreadsheet row.

Column order here matches the sheet the team already fills in by hand, so the
generated export drops straight into the existing workflow. Both the Google
Sheets sync and the CSV export import from here — if the two ever disagreed on
column order, the weekly sheet would silently scramble.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from app.models.business import Business
from app.models.lead import Lead

# Header row, in order. Changing this changes the sheet layout — if you add a
# column, add it to _row_values() at the same position.
SHEET_COLUMNS: tuple[str, ...] = (
    "Lead ID",
    "Business Name",
    "Business Type",
    "Country",
    "City",
    "Address",
    "Phone Number",
    "Email",
    "Website Available",
    "Website URL",
    "Owner/Manager Name",
    "Social Media Links",
    "Order Method",
    "Delivery System",
    "Automation Status",
    "Google Rating",
    "Reviews Count",
    "Lead Priority",
    "Notes",
    "Call Status",
    "Follow-up Date",
    "Week Number",
)

# What an empty cell reads as. Matches what the team typed manually, so a
# generated sheet and a hand-filled one look identical.
BLANK = "Not Available"


def _text(value: Any, blank: str = BLANK) -> str:
    """Render a scalar for a spreadsheet cell."""
    if value is None:
        return blank
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or blank
    return str(value)


def _enum_text(value: Any) -> str:
    """
    Render an enum as human-readable text.

    AutomationStatus.not_started -> "Not Started". The DB stores snake_case;
    nobody wants to read that in a spreadsheet.
    """
    if value is None:
        return BLANK
    raw = getattr(value, "value", value)
    return str(raw).replace("_", " ").title()


def _social_links(business: Optional[Business]) -> str:
    """Collapse the four social columns into one cell, as in the team's sheet."""
    if business is None:
        return "N/A"

    links = [
        business.facebook_url,
        business.instagram_url,
        business.linkedin_url,
        f"wa.me/{business.whatsapp_number}" if business.whatsapp_number else None,
    ]
    present = [link.strip() for link in links if link and link.strip()]
    return " | ".join(present) if present else "N/A"


def lead_to_row(lead: Lead) -> list[str]:
    """
    Flatten a Lead (plus its Business) into one spreadsheet row.

    Tolerates a missing business relationship: a Lead should always have one,
    but a half-written record must not take the whole weekly export down.
    """
    business = lead.business

    return [
        _text(lead.lead_ref, blank=""),
        _text(getattr(business, "name", None)),
        _text(getattr(business, "business_type", None)),
        _text(getattr(business, "country", None)),
        _text(getattr(business, "city", None)),
        _text(getattr(business, "address", None)),
        _text(getattr(business, "phone", None)),
        _text(getattr(business, "email", None)),
        _text(bool(getattr(business, "website_available", False))),
        _text(getattr(business, "website", None), blank="N/A"),
        _text(getattr(business, "owner_manager_name", None)),
        _social_links(business),
        # Prefer the original sheet phrasing when we have it; the enum is a
        # lossy summary of it.
        _text(lead.order_method_detail) if lead.order_method_detail else _enum_text(lead.order_method),
        _text(lead.delivery_system, blank="Unknown"),
        _text(lead.automation_status_detail) if lead.automation_status_detail else _enum_text(lead.automation_status),
        _text(getattr(business, "rating", None), blank=""),
        _text(getattr(business, "reviews_count", None), blank=""),
        _enum_text(lead.priority),
        _text(lead.notes, blank=""),
        _enum_text(lead.call_status),
        _text(lead.follow_up_date, blank="N/A"),
        _text(lead.week_number, blank=""),
    ]


def rows_for_leads(leads: list[Lead]) -> list[list[str]]:
    """Map a batch of leads to rows, header excluded."""
    return [lead_to_row(lead) for lead in leads]
