"""
Import leads from the team's hand-filled CSV/Excel sheet into PostgreSQL.

Every row goes through upsert_business(), so importing the same file twice —
or importing two interns' sheets that both contain the same shop — merges
rather than duplicates. That makes this safe to re-run, which matters because
the sheets are still being edited.

Accepts the column headers from the team's existing sheet, case-insensitively,
with common variants mapped (see _HEADER_ALIASES).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as pd

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.lead import (
    AutomationStatus,
    CallStatus,
    Lead,
    LeadPriority,
    OrderMethod,
)
from app.services.dedup import upsert_business

logger = logging.getLogger(__name__)

_WHITESPACE = re.compile(r"\s+")

# Values that mean "nothing here". Collected from the interns' actual sheets:
# "nan" comes from pandas exports, "unkown" is a real recurring typo, "—" is
# an em dash people type for blank, and "available on website" / "not listed"
# appear in the Phone column where someone couldn't find a number.
_BLANKS = {
    "", "n/a", "na", "n.a", "not available", "none", "null", "nil",
    "-", "--", "—", "–",
    "unknown", "unkown", "not found", "notfound", "not listed", "not given",
    "nan", "nat", "#value!", "#n/a",
    "available", "available on website", "multiple", "tbd", "tbc", "?",
    "to verify", "to be verified", "verify", "pending",
}

# Sheet header -> model field. Keys are lowercased and stripped before lookup.
_HEADER_ALIASES: dict[str, str] = {
    "lead id": "lead_ref",
    "business name": "name",
    "business type": "business_type",
    "country": "country",
    "city": "city",
    "address": "address",
    "phone number": "phone",
    "phone": "phone",
    "email": "email",
    "website available": "website_available",
    "website url": "website",
    "website": "website",
    "owner/manager name": "owner_manager_name",
    "owner manager name": "owner_manager_name",
    "social media links": "social_media_links",
    "order method": "order_method",
    "delivery system": "delivery_system",
    "automation status": "automation_status",
    "google rating": "rating",
    "rating": "rating",
    "reviews count": "reviews_count",
    "lead priority": "priority",
    "priority": "priority",
    "notes": "notes",
    "call status": "call_status",
    "follow-up date": "follow_up_date",
    "follow up date": "follow_up_date",
    "week number": "week_number",
    "assigned to": "assigned_to",
    "intern": "assigned_to",
    # Columns produced by the Google Maps Discovery Bot's CSV/JSON export
    # (app/bots/google_maps.py), so its output imports without a conversion
    # step. Its field names differ from the team's sheet headers.
    "category": "business_type",
    "google_rating": "rating",
    "reviews_count": "reviews_count",
    "maps_url": "maps_url",
    "place_id": "place_id",
    "source": "source_bot",
}


def _clean(value: Any) -> Optional[str]:
    """Normalize a cell to a string or None."""
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in _BLANKS else text


def _to_float(value: Any) -> Optional[float]:
    text = _clean(value)
    if text is None:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _to_int(value: Any) -> Optional[int]:
    """
    Parse a count, tolerating the approximations people write.

    "120+" and "800+" appear throughout the review-count column; taking the
    number and dropping the "+" is better than losing the value entirely.
    """
    text = _clean(value)
    if text is None:
        return None

    digits = re.sub(r"[^\d.]", "", text)
    if not digits:
        return None
    try:
        return int(float(digits))
    except ValueError:
        return None


def _to_week_number(value: Any) -> Optional[int]:
    """
    Parse the week column, which every intern formatted differently:
    "30", "52", "Week 1", "week1".

    Values outside 1-53 are rejected rather than stored, since a nonsense week
    would quietly corrupt the weekly dashboard's totals.
    """
    text = _clean(value)
    if text is None:
        return None

    match = re.search(r"\d+", text)
    if not match:
        return None

    week = int(match.group())
    if 1 <= week <= 53:
        return week

    logger.warning("Week number %r out of range 1-53 — leaving blank", text)
    return None


# Excel silently converts long phone numbers to scientific notation
# ("4.41317E+11"), which destroys digits that cannot be recovered.
_SCIENTIFIC_NOTATION = re.compile(r"^\d(\.\d+)?[eE][+-]?\d+$")


def _to_phone(value: Any) -> Optional[str]:
    """
    Clean a phone number, refusing values Excel has already corrupted.

    Guessing at the missing digits would be worse than a blank: a wrong number
    looks callable, and dedup would match two unrelated shops on it.
    """
    text = _clean(value)
    if text is None:
        return None

    if _SCIENTIFIC_NOTATION.match(text.replace(" ", "")):
        logger.warning(
            "Phone %r was mangled into scientific notation by Excel and can't be "
            "recovered — importing as blank. Re-enter it in the source sheet as text.",
            text,
        )
        return None

    # Needs at least a few digits to be a phone number at all.
    return text if len(re.sub(r"\D", "", text)) >= 7 else None


def _to_bool(value: Any) -> bool:
    text = (_clean(value) or "").lower()
    return text in {"yes", "y", "true", "1"}


def _to_date(value: Any):
    text = _clean(value)
    if text is None:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    logger.warning("Unparseable follow-up date %r — leaving blank", text)
    return None


def _to_enum(enum_cls, value: Any, default):
    """
    Map a sheet cell to an enum member.

    The sheet holds display text ("Not Started", "In Person"); the DB holds
    snake_case. Falls back to the default rather than failing the import —
    one odd cell shouldn't cost the whole file.
    """
    text = _clean(value)
    if text is None:
        return default

    normalized = text.lower().replace(" ", "_").replace("-", "_")
    for member in enum_cls:
        if member.value == normalized or member.name == normalized:
            return member

    logger.warning("Unrecognised %s value %r — using %s", enum_cls.__name__, text, default)
    return default


# The sheet writes call status as a phrase, sometimes with an en dash
# ("Contacted – Interested"). Keys here are compared after lowercasing and
# stripping everything that isn't a letter or a space.
_CALL_STATUS_ALIASES: dict[str, CallStatus] = {
    "not contacted": CallStatus.not_contacted,
    "not called": CallStatus.not_contacted,
    "uncontacted": CallStatus.not_contacted,
    "contacted": CallStatus.contacted,
    "called": CallStatus.contacted,
    "contacted interested": CallStatus.interested,
    "interested": CallStatus.interested,
    "contacted not interested": CallStatus.not_interested,
    "not interested": CallStatus.not_interested,
    "no answer": CallStatus.no_answer,
    "no response": CallStatus.no_answer,
    "attempted no answer": CallStatus.no_answer,
    "attempted": CallStatus.no_answer,
    "tried no answer": CallStatus.no_answer,
    "callback": CallStatus.callback_scheduled,
    "callback scheduled": CallStatus.callback_scheduled,
    "call back": CallStatus.callback_scheduled,
    "follow up": CallStatus.callback_scheduled,
}


def _to_call_status(value: Any) -> CallStatus:
    """Map the sheet's call-status phrasing onto the enum."""
    text = _clean(value)
    if text is None:
        return CallStatus.not_contacted

    # Collapse punctuation so "Contacted – Interested", "Contacted-Interested"
    # and "contacted / interested" all reduce to the same key.
    key = _WHITESPACE.sub(" ", re.sub(r"[^a-z ]", " ", text.lower())).strip()

    if key in _CALL_STATUS_ALIASES:
        return _CALL_STATUS_ALIASES[key]

    logger.warning("Unrecognised call status %r — using Not Contacted", text)
    return CallStatus.not_contacted


# The sheet's Automation Status describes the business, not our task progress.
_AUTOMATION_ALIASES: dict[str, AutomationStatus] = {
    "manual": AutomationStatus.not_started,
    "semi automated": AutomationStatus.in_progress,
    "semiautomated": AutomationStatus.in_progress,
    "partially automated": AutomationStatus.in_progress,
    "automated": AutomationStatus.completed,
    "fully automated": AutomationStatus.completed,
}


def _coarse_automation_status(detail: Optional[str]) -> AutomationStatus:
    """
    Collapse "Manual" / "Semi Automated" / "Automated" onto the AI service's
    enum, so the dashboard can still filter on it.

    Manual businesses are the *best* leads (most to gain from automation), so
    getting this mapping right matters for prioritisation.
    """
    if not detail:
        return AutomationStatus.not_started

    key = _WHITESPACE.sub(" ", re.sub(r"[^a-z ]", " ", detail.lower())).strip()
    if key in _AUTOMATION_ALIASES:
        return _AUTOMATION_ALIASES[key]

    # People add qualifiers the exact-match table can't anticipate:
    # "Manual (likely)", "Mostly automated", "Semi-automated?". Fall back to
    # the distinguishing word. "semi" is checked before "automat" because
    # "semi automated" contains both.
    if "semi" in key or "partial" in key:
        return AutomationStatus.in_progress
    if "manual" in key:
        return AutomationStatus.not_started
    if "automat" in key:
        return AutomationStatus.completed

    return _to_enum(AutomationStatus, detail, AutomationStatus.not_started)


def _coarse_order_method(detail: Optional[str]) -> OrderMethod:
    """
    Collapse the sheet's free-text order method into the AI service's enum.

    The enum is what the dashboard filters on, so it has to be populated even
    though the readable text is kept alongside it in order_method_detail.
    """
    if not detail:
        return OrderMethod.unknown

    text = detail.lower()
    if "website" in text or "online" in text or "mobile" in text or "app" in text:
        return OrderMethod.online
    if "phone" in text or "call" in text or "whatsapp" in text:
        return OrderMethod.phone
    if "walk" in text or "in-store" in text or "in store" in text:
        return OrderMethod.in_person
    return OrderMethod.unknown


def _split_social(value: Any) -> dict[str, Optional[str]]:
    """
    Split the sheet's combined "Social Media Links" cell back into columns.

    Links are separated by "|" or "," and routed by the domain they contain.
    """
    result: dict[str, Optional[str]] = {
        "facebook_url": None,
        "instagram_url": None,
        "linkedin_url": None,
        "whatsapp_number": None,
    }

    text = _clean(value)
    if text is None:
        return result

    for part in (p.strip() for p in text.replace(",", "|").split("|")):
        if not part:
            continue
        lowered = part.lower()
        if "facebook" in lowered or "fb.com" in lowered:
            result["facebook_url"] = part
        elif "instagram" in lowered:
            result["instagram_url"] = part
        elif "linkedin" in lowered:
            result["linkedin_url"] = part
        elif "wa.me" in lowered or "whatsapp" in lowered:
            result["whatsapp_number"] = part.rsplit("/", 1)[-1]

    return result


def _normalize_headers(row: Mapping) -> dict:
    """
    Rename a raw sheet row's keys to model field names.

    Accepts a plain dict or a pandas Series, so callers can pass a DataFrame
    row directly.
    """
    normalized: dict[str, Any] = {}
    for raw_key, value in row.items():
        if raw_key is None:
            continue
        field = _HEADER_ALIASES.get(str(raw_key).strip().lower())
        if field:
            normalized[field] = value
    return normalized


def import_row(db: Session, raw_row: Mapping, *, assigned_to: Optional[str] = None) -> tuple[Optional[Lead], bool]:
    """
    Import one sheet row.

    Returns (lead, created_business). `lead` is None for a row with no usable
    business name — a trailing blank line in the CSV, typically.
    """
    row = _normalize_headers(raw_row)

    name = _clean(row.get("name"))
    if not name:
        return None, False

    social = _split_social(row.get("social_media_links"))

    business = Business(
        name=name,
        city=_clean(row.get("city")),
        country=_clean(row.get("country")),
        business_type=_clean(row.get("business_type")),
        address=_clean(row.get("address")),
        phone=_to_phone(row.get("phone")),
        email=_clean(row.get("email")),
        website=_clean(row.get("website")),
        owner_manager_name=_clean(row.get("owner_manager_name")),
        rating=_to_float(row.get("rating")),
        reviews_count=_to_int(row.get("reviews_count")),
        place_id=_clean(row.get("place_id")),
        maps_url=_clean(row.get("maps_url")),
        source_bot=_clean(row.get("source_bot")) or "manual_import",
        assigned_to=assigned_to or _clean(row.get("assigned_to")),
        **social,
    )

    business, created = upsert_business(db, business, commit=False)
    db.flush()  # need business.id before attaching the Lead

    lead = db.query(Lead).filter(Lead.business_id == business.id).first()
    if lead is None:
        lead = Lead(business_id=business.id)
        db.add(lead)

    lead.order_method_detail = _clean(row.get("order_method"))
    lead.order_method = _coarse_order_method(lead.order_method_detail)
    lead.automation_status_detail = _clean(row.get("automation_status"))
    lead.automation_status = _coarse_automation_status(lead.automation_status_detail)
    lead.priority = _to_enum(LeadPriority, row.get("priority"), LeadPriority.medium)
    lead.call_status = _to_call_status(row.get("call_status"))
    lead.delivery_system = _clean(row.get("delivery_system"))
    lead.notes = _clean(row.get("notes"))
    lead.follow_up_date = _to_date(row.get("follow_up_date"))
    lead.week_number = _to_week_number(row.get("week_number"))

    return lead, created


def import_rows(
    db: Session,
    rows: Iterable[Mapping],
    *,
    assigned_to: Optional[str] = None,
    commit: bool = True,
) -> dict:
    """Import an iterable of dict rows. Returns a summary."""
    created = merged = skipped = 0

    for raw_row in rows:
        lead, was_created = import_row(db, raw_row, assigned_to=assigned_to)
        if lead is None:
            skipped += 1
        elif was_created:
            created += 1
        else:
            merged += 1

    if commit:
        db.commit()

    summary = {"created": created, "merged_as_duplicate": merged, "skipped": skipped}
    logger.info("Import finished: %s", summary)
    return summary


def read_sheet(path: str | Path) -> "pd.DataFrame":
    """
    Load a .csv or .xlsx lead sheet into a DataFrame.

    Everything is read as text (`dtype=str`). Pandas would otherwise infer
    types per column, and on these sheets that does real damage: a phone
    column becomes float and "+44 117 952 4240" turns into scientific
    notation, which is exactly the corruption we're trying to survive.
    Conversion happens later, per field, in the _to_* helpers.
    """
    import pandas as pd

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")

    suffix = path.suffix.lower()

    if suffix == ".csv":
        # utf-8-sig strips the BOM Excel writes, which would otherwise corrupt
        # the first header ("﻿Lead ID") and break the alias lookup.
        return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")

    if suffix in {".xlsx", ".xlsm"}:
        try:
            return pd.read_excel(path, dtype=str, keep_default_na=False)
        except ImportError as exc:
            raise RuntimeError(
                "Reading .xlsx needs openpyxl — run: pip install -r requirements.txt "
                "(or save the sheet as .csv and import that)"
            ) from exc

    raise ValueError(f"Unsupported file type {suffix!r} — use .csv or .xlsx")


def import_dataframe(
    db: Session,
    frame: "pd.DataFrame",
    *,
    assigned_to: Optional[str] = None,
    commit: bool = True,
) -> dict:
    """
    Import a DataFrame of sheet rows.

    Separate from read_sheet() so the same path serves a file on disk, a
    spreadsheet pasted into the dashboard, or a frame built in a test.
    """
    # Drop rows that are entirely empty. Trailing blank lines are common in
    # hand-maintained sheets and would otherwise be counted as skipped.
    cleaned = frame.dropna(how="all")

    return import_rows(
        db,
        (row for _, row in cleaned.iterrows()),
        assigned_to=assigned_to,
        commit=commit,
    )


def import_file(db: Session, path: str | Path, *, assigned_to: Optional[str] = None) -> dict:
    """Import a .csv or .xlsx lead sheet."""
    return import_dataframe(db, read_sheet(path), assigned_to=assigned_to)
