"""
Duplicate detection for scraped businesses.

Three bots write into the same `businesses` table and none of them coordinate:
the Google Maps bot finds "Wah Yan Hong", the website scraper later finds
"Wah Yan Hong Supermarket Ltd" from the site's <title>, and a second city sweep
finds the same shop again with a differently formatted phone number. Without
this module every re-run of the pipeline inflates the lead count.

Strategy, cheapest check first:

  1. Exact match on a normalized key (phone, then domain, then city+name).
     Covers the overwhelming majority — same shop, cosmetically different text.
  2. Fuzzy match on name within the same city, using Postgres pg_trgm
     similarity. Covers suffix noise ("Ltd", "Supermarket", "& Cafe").

Matches are recorded, never destroyed: the duplicate row stays in the table
with is_duplicate=True and duplicate_of_id pointing at the survivor. Exports
filter duplicates out. This means a bad merge is a one-line UPDATE to undo,
which matters because fuzzy matching will occasionally be wrong.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, Optional
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.business import Business

# Similarity above which two names in the same city are considered the same
# business. Tuned on the team's Bristol/Dubai sheet: 0.82 merges
# "Wah Yan Hong" / "Wah Yan Hong Supermarket" but keeps "Better Food" and
# "Best Food" apart. Raise it if QA reports wrong merges.
NAME_SIMILARITY_THRESHOLD = 0.82

# Words that carry no identifying information in a business name. Stripped
# before comparison so "Tesco Superstore" and "Tesco Store" collapse together.
_NOISE_WORDS = {
    "ltd", "limited", "llc", "inc", "incorporated", "co", "company",
    "the", "and",
    "supermarket", "hypermarket", "market", "mart", "minimart", "store",
    "shop", "grocery", "groceries", "superstore", "cafe", "trading",
    "foods", "food", "llp", "pvt", "private", "est", "establishment",
}

_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_WHITESPACE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_name(name: Optional[str]) -> Optional[str]:
    """
    Reduce a business name to its identifying words.

    "Wai Yee Hong Chinese Supermarket Ltd." -> "chinese hong wai yee"

    Words are sorted so word-order differences between sources ("Asian Market
    QKO" vs "QKO Asian Market") still collapse to the same key.
    """
    if not name:
        return None

    lowered = _NON_ALNUM.sub(" ", name.lower())
    words = [w for w in _WHITESPACE.split(lowered) if w and w not in _NOISE_WORDS]

    if not words:
        # Name was entirely noise words (e.g. "The Mini Mart"). Falling back to
        # the raw text is better than returning None, which would disable
        # dedup for this record entirely.
        words = [w for w in _WHITESPACE.split(lowered) if w]

    return " ".join(sorted(words)) or None


# Country codes in scope, longest first so "971" is tested before "97"/"92"
# could ever partially match it.
_COUNTRY_CODES = ("971", "966", "974", "968", "973", "965", "92", "44")


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Reduce a phone number to its national digits, so the same shop matches
    however the number was written down.

    "+44 117 952 4240" and "0117 952 4240"   -> "1179524240"
    "+971 50 110 4711" and "050 110 4711"    -> "501104711"

    Country code and trunk zero are stripped explicitly rather than by taking
    the last N digits: national numbers aren't a fixed length across the
    countries in scope (UK 10, UAE 9, PK 10), so a fixed-width slice leaves a
    stray country-code digit on the front of the shorter ones and the two
    formats of the same UAE number stop matching.
    """
    if not phone:
        return None

    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        # Too short to be a real number — extension, or scraping noise.
        return None

    # Handles both the "00" international prefix and a national trunk zero.
    digits = digits.lstrip("0")

    for code in _COUNTRY_CODES:
        # Only strip if enough digits remain to still be a phone number,
        # otherwise a national number that happens to start with "44" would
        # be truncated.
        if digits.startswith(code) and len(digits) - len(code) >= 8:
            digits = digits[len(code):]
            break

    return digits.lstrip("0") or None


def normalize_domain(website: Optional[str]) -> Optional[str]:
    """
    Reduce a website URL to a bare domain.

    "https://www.WaiYeeHong.com/contact?x=1" -> "waiyeehong.com"

    Returns None for the placeholder values the team types into the sheet
    ("N/A", "Not Available") so they never match each other.
    """
    if not website:
        return None

    candidate = website.strip().lower()
    if candidate in {"n/a", "na", "not available", "none", "-", ""}:
        return None

    if "://" not in candidate:
        candidate = f"http://{candidate}"

    host = urlparse(candidate).netloc or ""
    host = host.split("@")[-1].split(":")[0]  # strip credentials and port

    if host.startswith("www."):
        host = host[4:]

    # A bare hostname with no dot isn't a real domain.
    return host if host and "." in host else None


def set_dedup_keys(business: Business) -> Business:
    """Populate the normalized key columns. Idempotent; call before every save."""
    business.name_key = normalize_name(business.name)
    business.phone_key = normalize_phone(business.phone)
    business.domain_key = normalize_domain(business.website)
    business.set_derived_fields()
    return business


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

# Non-geographic numbers: one line shared by every branch of a chain, so they
# identify the *company*, not the shop. Seen in the team's sheets on Tesco
# (0345...), Heron and ALDI (0800...), and Al Fatah's Pakistani UAN
# (042-111-933-933), which merged two branches 300km apart.
_UK_SERVICE_PREFIXES = ("300", "303", "306", "330", "333", "343", "344", "345",
                        "370", "371", "372", "800", "808", "843", "844", "845",
                        "870", "871", "872", "500")
_UAE_SERVICE_PREFIXES = ("800",)
# Pakistani UAN: area code, then 111, then six digits.
_PK_UAN = re.compile(r"^\d{2,3}111\d{6}$")


def is_shared_line(phone_key: Optional[str]) -> bool:
    """
    True if a normalized phone is a chain-wide service number.

    These must never be used as a dedup signal on their own — every branch
    publishes the same one, so matching on it merges unrelated shops.
    """
    if not phone_key:
        return False
    if _PK_UAN.match(phone_key):
        return True
    return phone_key.startswith(_UK_SERVICE_PREFIXES + _UAE_SERVICE_PREFIXES)


# A phone match still needs the names to be at least loosely consistent.
# Calibrated on the real sheets: "C-Mart Askari 14" and "Save Mart Lalazar"
# were given the same number by mistake and score 0.35, while genuine matches
# like "Wah Yan Hong" / "W Y Hong Oriental Foods" score 0.55.
_PHONE_CORROBORATION_THRESHOLD = 0.45


# A name must have at least this many meaningful words before we'll treat
# "all its words appear in the other name" as proof they're the same business.
# One-word names are too weak: "Mini Market" -> {mini} would otherwise swallow
# every other shop in the city whose name contains "mini".
_MIN_TOKENS_FOR_CONTAINMENT = 2


def name_similarity(a: Optional[str], b: Optional[str]) -> float:
    """
    Similarity between two normalized names, 0.0-1.0.

    Combines two measures, taking whichever is higher:

      * character similarity, which catches typos and spelling drift
        ("Baqer Mohebi" / "Bager Mohebi");
      * token containment, which catches one source having extra descriptive
        words ("Wai Yee Hong" vs "Wai Yee Hong Chinese"). Character similarity
        alone scores that pair ~0.75 and misses it, because the extra word
        drags the ratio down even though every word of the shorter name is
        present in the longer one.

    Containment is gated on _MIN_TOKENS_FOR_CONTAINMENT so short generic names
    can't over-merge.
    """
    if not a or not b:
        return 0.0

    character_ratio = SequenceMatcher(None, a, b).ratio()

    tokens_a, tokens_b = set(a.split()), set(b.split())
    shorter = min(len(tokens_a), len(tokens_b))

    if shorter >= _MIN_TOKENS_FOR_CONTAINMENT:
        containment = len(tokens_a & tokens_b) / shorter
        return max(character_ratio, containment)

    return character_ratio


def _fuzzy_candidates(db: Session, business: Business) -> Iterable[Business]:
    """
    Businesses in the same city whose name might be the same business.

    Scoped to the city because a fuzzy scan across the whole table would be
    both slow and wrong — "Al Maya" in Dubai and "Al Maya" in Sharjah are
    different branches the team tracks separately.
    """
    if not business.name_key or not business.city:
        return []

    query = db.query(Business).filter(
        Business.city == business.city,
        Business.is_duplicate.is_(False),
    )
    if business.id is not None:
        query = query.filter(Business.id != business.id)

    return query.all()


def find_duplicate(db: Session, business: Business) -> Optional[Business]:
    """
    Return the existing Business this one duplicates, or None.

    `business` may be unsaved. Keys are computed on the fly, so callers don't
    have to remember to call set_dedup_keys() first.
    """
    name_key = business.name_key or normalize_name(business.name)
    phone_key = business.phone_key or normalize_phone(business.phone)
    domain_key = business.domain_key or normalize_domain(business.website)

    base = db.query(Business).filter(Business.is_duplicate.is_(False))
    if business.id is not None:
        base = base.filter(Business.id != business.id)

    # 0. Google's place_id is definitive when both records have one — it's
    #    Google's own identifier for the physical location, so no heuristic
    #    can beat it. Only the Maps bot supplies it.
    if business.place_id:
        match = base.filter(Business.place_id == business.place_id).first()
        if match:
            return match

    # 1. Phone, corroborated. A shared direct line is strong evidence, but it
    #    needs two guards learned from the real sheets:
    #      - skip chain-wide service numbers entirely (see is_shared_line);
    #      - require the same city and a loosely similar name, because a
    #        number typed against the wrong shop otherwise merges two
    #        unrelated businesses and there's no way to notice.
    if phone_key and not is_shared_line(phone_key):
        for candidate in base.filter(Business.phone_key == phone_key).all():
            if candidate.city != business.city:
                continue
            if name_similarity(name_key, candidate.name_key) >= _PHONE_CORROBORATION_THRESHOLD:
                return candidate

    # 2. Same website domain. Weaker than phone: chains share a domain across
    #    branches, so require the city to agree too.
    if domain_key:
        match = base.filter(
            Business.domain_key == domain_key,
            Business.city == business.city,
        ).first()
        if match:
            return match

    # 3. Exact normalized name within the city.
    if name_key and business.city:
        match = base.filter(
            Business.name_key == name_key,
            Business.city == business.city,
        ).first()
        if match:
            return match

    # 4. Fuzzy name within the city.
    if name_key and business.city:
        best, best_score = None, 0.0
        for candidate in _fuzzy_candidates(db, business):
            score = name_similarity(name_key, candidate.name_key)
            if score > best_score:
                best, best_score = candidate, score
        if best is not None and best_score >= NAME_SIMILARITY_THRESHOLD:
            return best

    return None


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

# Fields a later bot is allowed to fill in on an existing record. Order of
# arrival isn't guaranteed, so we only ever fill blanks — a scraper must not
# overwrite a value a human corrected in the dashboard.
_ENRICHABLE_FIELDS = (
    "address", "phone", "website", "rating", "reviews_count",
    "email", "contact_page_url",
    "facebook_url", "instagram_url", "whatsapp_number", "linkedin_url",
    "business_type", "country", "owner_manager_name", "assigned_to",
    "place_id", "maps_url",
)


def merge_into(existing: Business, incoming: Business) -> Business:
    """
    Copy any field the existing record is missing from the incoming one.

    Blank-only fill, never overwrite. Returns the existing record.
    """
    for field in _ENRICHABLE_FIELDS:
        current = getattr(existing, field, None)
        new_value = getattr(incoming, field, None)

        is_blank = current is None or (isinstance(current, str) and not current.strip())
        has_value = new_value is not None and (not isinstance(new_value, str) or new_value.strip())

        if is_blank and has_value:
            setattr(existing, field, new_value)

    set_dedup_keys(existing)
    return existing


def upsert_business(db: Session, incoming: Business, *, commit: bool = True) -> tuple[Business, bool]:
    """
    Insert `incoming`, or merge it into the business it duplicates.

    Returns (business, created). `created` is False when the record was
    recognised as a duplicate and merged instead of inserted — bots can use
    that to decide whether to queue AI classification.

    This is the single entry point every bot should use instead of
    `db.add(Business(...))`.
    """
    set_dedup_keys(incoming)

    existing = find_duplicate(db, incoming)
    if existing is not None:
        merge_into(existing, incoming)
        if commit:
            db.commit()
            db.refresh(existing)
        return existing, False

    db.add(incoming)
    if commit:
        db.commit()
        db.refresh(incoming)
    return incoming, True


def mark_as_duplicate(db: Session, duplicate: Business, survivor: Business, *, commit: bool = True) -> Business:
    """
    Flag an already-saved record as a duplicate of another, merging its data in.

    Used by the backfill pass below and by the QA "merge these two" action,
    where both rows already exist in the table.
    """
    merge_into(survivor, duplicate)
    duplicate.is_duplicate = True
    duplicate.duplicate_of_id = survivor.id

    if commit:
        db.commit()
    return survivor


def backfill_duplicates(db: Session, *, commit: bool = True) -> int:
    """
    One-off sweep over existing rows, for data inserted before dedup existed.

    Processes oldest-first so the earliest record wins and stays the survivor.
    Returns the number of rows newly flagged as duplicates.
    """
    flagged = 0
    businesses = (
        db.query(Business)
        .filter(Business.is_duplicate.is_(False))
        .order_by(Business.created_at.asc().nullsfirst())
        .all()
    )

    seen: list[Business] = []
    for business in businesses:
        set_dedup_keys(business)

        match = None
        for candidate in seen:
            if _is_same(business, candidate):
                match = candidate
                break

        if match is not None:
            merge_into(match, business)
            business.is_duplicate = True
            business.duplicate_of_id = match.id
            flagged += 1
        else:
            seen.append(business)

    if commit:
        db.commit()
    return flagged


def _is_same(a: Business, b: Business) -> bool:
    """In-memory version of find_duplicate's rules, used by the backfill sweep."""
    if a.place_id and a.place_id == b.place_id:
        return True
    if (
        a.phone_key
        and a.phone_key == b.phone_key
        and not is_shared_line(a.phone_key)
        and a.city == b.city
        and name_similarity(a.name_key, b.name_key) >= _PHONE_CORROBORATION_THRESHOLD
    ):
        return True
    if a.domain_key and a.domain_key == b.domain_key and a.city == b.city:
        return True
    if a.city != b.city:
        return False
    if a.name_key and a.name_key == b.name_key:
        return True
    return name_similarity(a.name_key, b.name_key) >= NAME_SIMILARITY_THRESHOLD


def ensure_pg_trgm(db: Session) -> bool:
    """
    Enable the pg_trgm extension, used to push fuzzy matching into Postgres.

    Returns False (rather than raising) when the DB isn't Postgres or the role
    lacks CREATE EXTENSION rights — the Python fallback in name_similarity()
    handles those cases, just more slowly.
    """
    try:
        db.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        db.commit()
        return True
    except SQLAlchemyError:
        db.rollback()
        return False
