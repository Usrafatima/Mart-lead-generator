"""Tests for duplicate detection — app/services/dedup.py."""

import pytest

from app.services.dedup import (
    NAME_SIMILARITY_THRESHOLD,
    backfill_duplicates,
    find_duplicate,
    is_shared_line,
    merge_into,
    name_similarity,
    normalize_domain,
    normalize_name,
    normalize_phone,
    set_dedup_keys,
    upsert_business,
)


# --- normalization ---------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Wai Yee Hong Chinese Supermarket Ltd.", "chinese hong wai yee"),
        ("QKO Asian Market", "asian qko"),
        ("Asian Market QKO", "asian qko"),  # word order must not matter
        ("Tesco Superstore", "tesco"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


def test_normalize_name_all_noise_words_falls_back():
    # "The Food Store" is entirely noise words; returning None would disable
    # dedup for the record, so we keep the raw words instead.
    assert normalize_name("The Food Store") == "food store the"


def test_normalize_name_keeps_one_word_when_the_rest_is_noise():
    assert normalize_name("The Mini Mart") == "mini"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+44 117 952 4240", "1179524240"),
        ("0117 952 4240", "1179524240"),      # same number, UK trunk-zero form
        ("0044 117 952 4240", "1179524240"),  # and the 00 international prefix
        ("+971 50 110 4711", "501104711"),
        ("050 110 4711", "501104711"),        # same UAE number, local form
        ("+92 300 1234567", "3001234567"),
        ("123", None),                        # too short to be real
        ("Not Available", None),
        (None, None),
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_uae_number_matches_across_international_and_local_form():
    # Regression: a fixed-width "last 10 digits" slice left the trailing "1"
    # of +971 on the international form, so these two stopped matching.
    assert normalize_phone("+971 50 110 4711") == normalize_phone("050 110 4711")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.WaiYeeHong.com/contact?x=1", "waiyeehong.com"),
        ("waiyeehong.com", "waiyeehong.com"),
        ("http://user:pw@shop.co.uk:8080/x", "shop.co.uk"),
        ("N/A", None),
        ("Not Available", None),
        ("localhost", None),   # no dot, not a real domain
        (None, None),
    ],
)
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


def test_placeholder_domains_do_not_match_each_other():
    # Regression guard: the sheet is full of "N/A" websites. If those
    # normalized to a shared key, every website-less shop in a city would
    # collapse into one lead.
    assert normalize_domain("N/A") is None
    assert normalize_domain("Not Available") is None


# --- matching --------------------------------------------------------------

def test_exact_phone_match_wins_across_different_names(db, make_business):
    original = make_business("Wah Yan Hong", phone="+44 117 929 7269")
    upsert_business(db, original)

    # Same landline, name scraped differently by another bot.
    incoming = make_business("W Y Hong Oriental Foods", phone="0117 929 7269")
    assert find_duplicate(db, incoming) is not None


def test_shared_phone_does_not_merge_unrelated_shops(db, make_business):
    # From Usman's real sheet: the same number was typed against two
    # different Rawalpindi shops. Merging them loses a genuine lead.
    upsert_business(db, make_business("C-Mart Askari 14", city="Rawalpindi", phone="92 51 5156707"))

    incoming = make_business("Save Mart Lalazar", city="Rawalpindi", phone="92 51 5156707")
    assert find_duplicate(db, incoming) is None


def test_phone_match_requires_same_city(db, make_business):
    upsert_business(db, make_business("Al Fatah", city="Islamabad", phone="92 42 3111222"))

    incoming = make_business("Al Fatah", city="Faisalabad", phone="92 42 3111222")
    # Chain branches in different cities are separate leads.
    assert find_duplicate(db, incoming) is None


@pytest.mark.parametrize(
    "phone,shared",
    [
        ("+44 345 026 9343", True),   # Tesco's national service line
        ("+44 800 032 2424", True),   # Heron Foods freephone
        ("+92 42 111933933", True),   # Al Fatah's Pakistani UAN
        ("+971 800 12345678", True),  # UAE toll-free
        ("+44 117 952 4240", False),  # ordinary Bristol landline
        ("+92 51 5156707", False),    # ordinary Rawalpindi landline
    ],
)
def test_shared_line_detection(phone, shared):
    assert is_shared_line(normalize_phone(phone)) is shared


def test_chain_service_number_is_ignored_for_dedup(db, make_business):
    # Tesco, Heron and ALDI all publish 0800/0345 numbers. Without this guard
    # every chain in a city collapses into a single lead.
    upsert_business(db, make_business("Tesco Express Briggate", city="Leeds", phone="44 345 026 9343"))

    incoming = make_business("Iceland Foods Leeds", city="Leeds", phone="44 345 026 9343")
    assert find_duplicate(db, incoming) is None


def test_domain_match_requires_same_city(db, make_business):
    upsert_business(db, make_business("Al Maya", city="Dubai", website="almaya.ae"))

    same_city = make_business("Al Maya Marsa", city="Dubai", website="https://almaya.ae/x")
    other_city = make_business("Al Maya Sharjah", city="Sharjah", website="almaya.ae")

    assert find_duplicate(db, same_city) is not None
    # Different branches in different cities are tracked separately.
    assert find_duplicate(db, other_city) is None


def test_fuzzy_name_match_within_city(db, make_business):
    upsert_business(db, make_business("Wah Yan Hong", city="Bristol"))

    incoming = make_business("Wah Yan Hong Supermarket", city="Bristol")
    assert find_duplicate(db, incoming) is not None


def test_same_place_id_is_a_definitive_match(db, make_business):
    upsert_business(db, make_business("Clifton Mini Market", place_id="0x4871:0x1b5d"))

    # Name scraped differently on a later run, but Google says same place.
    incoming = make_business("Clifton Premier Store", place_id="0x4871:0x1b5d")
    assert find_duplicate(db, incoming) is not None


def test_different_place_id_vetoes_a_name_match(db, make_business):
    """
    From a live Bristol scrape: Google returned "International Mini Market"
    and "Albercik International mini Market" as separate places. Name
    containment merged them, losing a real lead. Google's verdict wins.
    """
    upsert_business(
        db, make_business("International Mini Market", place_id="0x48718fd8:0xfaf255e4")
    )

    incoming = make_business(
        "Albercik International mini Market", place_id="0x48718aaa:0xbbbbcccc"
    )
    assert find_duplicate(db, incoming) is None


def test_place_id_veto_does_not_block_hand_entered_rows(db, make_business):
    # Sheet rows have no place_id, so a scraped record must still be able to
    # match one — that's how manual and automated data get reconciled.
    upsert_business(db, make_business("Clifton Mini Market", phone="+44 117 973 1444"))

    incoming = make_business(
        "Clifton Mini Market", phone="+44 117 973 1444", place_id="0x4871:0x1b5d"
    )
    assert find_duplicate(db, incoming) is not None


def test_similar_but_distinct_names_are_not_merged(db, make_business):
    # "Better Food" and "Best Food" are different businesses in the sheet.
    upsert_business(db, make_business("Better Food", city="Bristol"))

    incoming = make_business("Best Food", city="Bristol")
    assert find_duplicate(db, incoming) is None


def test_same_name_different_city_is_not_a_duplicate(db, make_business):
    upsert_business(db, make_business("Tesco Superstore", city="Bristol"))

    incoming = make_business("Tesco Superstore", city="Manchester")
    assert find_duplicate(db, incoming) is None


def test_name_similarity_threshold_is_sane():
    assert name_similarity("hong wah yan", "hong wah yan") == 1.0
    assert name_similarity("hong wah yan", None) == 0.0
    assert name_similarity("better", "best") < NAME_SIMILARITY_THRESHOLD


def test_extra_descriptive_word_still_counts_as_the_same_business():
    # Character similarity alone scores this ~0.75 and misses it; token
    # containment is what catches it.
    assert name_similarity("hong wai yee", "chinese hong wai yee") >= NAME_SIMILARITY_THRESHOLD


def test_containment_does_not_over_merge_one_word_names(db, make_business):
    # {mini} is contained in {mini, super}, but a single generic word is not
    # enough evidence that these are the same shop.
    upsert_business(db, make_business("Mini Market", city="Bristol"))
    assert find_duplicate(db, make_business("Mini Super", city="Bristol")) is None


# --- upsert ----------------------------------------------------------------

def test_upsert_creates_then_merges(db, make_business):
    first, created = upsert_business(db, make_business("Nihow Asian", phone="+44 7737 027926"))
    assert created is True

    second, created_again = upsert_business(
        db, make_business("Nihow Asian Supermarket", phone="+44 7737 027926")
    )
    assert created_again is False
    assert second.id == first.id


def test_upsert_enriches_blank_fields_only(db, make_business):
    existing, _ = upsert_business(
        db, make_business("Matter Wholefoods", phone="+44 117 902 1915", email=None)
    )

    upsert_business(
        db,
        make_business(
            "Matter Wholefoods",
            phone="+44 117 902 1915",
            email="MatterBristol@gmail.com",
            website="matterwholefoods.uk",
        ),
    )
    db.refresh(existing)

    assert existing.email == "MatterBristol@gmail.com"
    assert existing.website == "matterwholefoods.uk"


def test_merge_never_overwrites_an_existing_value(db, make_business):
    # A human corrected the email in the dashboard; a later scrape must not
    # clobber it with a worse value.
    existing = make_business("Better Food", email="correct@betterfood.co.uk")
    incoming = make_business("Better Food", email="info@scraped-wrong.com")

    merge_into(existing, incoming)
    assert existing.email == "correct@betterfood.co.uk"


def test_website_available_is_derived_from_website(db, make_business):
    with_site = set_dedup_keys(make_business("A", website="example.com"))
    without = set_dedup_keys(make_business("B", website=None))
    blank = set_dedup_keys(make_business("C", website="   "))

    assert with_site.website_available is True
    assert without.website_available is False
    assert blank.website_available is False


# --- backfill --------------------------------------------------------------

def test_backfill_flags_duplicates_and_keeps_oldest(db, make_business):
    from app.models.business import Business

    # Inserted directly, bypassing dedup — simulates rows written before this
    # module existed.
    for name in ("Wai Yee Hong", "Wai Yee Hong Chinese Supermarket", "Better Food"):
        db.add(make_business(name, city="Bristol"))
    db.commit()

    flagged = backfill_duplicates(db)
    assert flagged == 1

    survivors = db.query(Business).filter(Business.is_duplicate.is_(False)).all()
    assert len(survivors) == 2

    duplicate = db.query(Business).filter(Business.is_duplicate.is_(True)).one()
    assert duplicate.duplicate_of_id is not None


def test_backfill_is_idempotent(db, make_business):
    for name in ("Wai Yee Hong", "Wai Yee Hong Chinese Supermarket"):
        db.add(make_business(name, city="Bristol"))
    db.commit()

    assert backfill_duplicates(db) == 1
    # Running it again must not re-flag anything.
    assert backfill_duplicates(db) == 0
