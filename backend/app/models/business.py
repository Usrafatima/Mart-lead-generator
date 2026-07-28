import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.core.database import Base, GUID


class Business(Base):
    """
    Raw business record, primarily created by the Google Maps Discovery Bot.
    Website/Social scraper bots enrich this same record rather than creating
    a new one, which is what lets us de-duplicate leads later.
    """

    __tablename__ = "businesses"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    name = Column(String, nullable=False, index=True)
    city = Column(String, index=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    website = Column(String, nullable=True)
    rating = Column(Float, nullable=True)

    # Columns matching the lead sheet the team fills in manually. All nullable
    # so the bots' existing BusinessCreate payload keeps working unchanged —
    # whatever isn't scraped stays NULL and shows as "Not Available" on export.
    business_type = Column(String, nullable=True, index=True)
    country = Column(String, nullable=True, index=True)
    owner_manager_name = Column(String, nullable=True)
    reviews_count = Column(Integer, nullable=True)

    # Derived, not scraped: set by set_derived_fields() below so the sheet's
    # "Website Available" column stays consistent with the website column.
    website_available = Column(Boolean, default=False, nullable=False)

    # Filled in later by Website Scraper Bot
    email = Column(String, nullable=True)
    contact_page_url = Column(String, nullable=True)

    # Filled in later by Social Media Scraper Bot
    facebook_url = Column(String, nullable=True)
    instagram_url = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)

    # Google's own stable identifier for a place, captured by the Maps bot.
    # This is the single most reliable dedup signal we have: two records with
    # the same place_id are definitively the same shop, no fuzzy matching
    # needed. Nullable because manually-imported sheet rows don't have one.
    place_id = Column(String, nullable=True, unique=True, index=True)
    maps_url = Column(String, nullable=True)

    # Normalized forms of name/phone/website used purely for duplicate
    # detection. Never display these — they're lossy on purpose. Written by
    # app.services.dedup.set_dedup_keys().
    name_key = Column(String, nullable=True, index=True)
    phone_key = Column(String, nullable=True, index=True)
    domain_key = Column(String, nullable=True, index=True)

    is_duplicate = Column(Boolean, default=False, nullable=False)
    # Points at the record this one duplicates. We keep duplicates instead of
    # deleting them so a wrong merge can be undone, and so we can show the
    # bots' raw output during QA. Exports filter on is_duplicate == False.
    duplicate_of_id = Column(GUID(), ForeignKey("businesses.id"), nullable=True)

    source_bot = Column(String, nullable=True)  # e.g. "google_maps_bot"
    # Which intern/city assignment this came from, for the weekly target report.
    assigned_to = Column(String, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead = relationship("Lead", back_populates="business", uselist=False)
    duplicate_of = relationship("Business", remote_side=[id], backref="duplicates")

    __table_args__ = (
        # The two lookups dedup does on every single insert.
        Index("ix_businesses_city_name_key", "city", "name_key"),
        Index("ix_businesses_country_city", "country", "city"),
    )

    def set_derived_fields(self) -> None:
        """Keep computed columns in sync. Call after mutating website."""
        self.website_available = bool(self.website and self.website.strip())

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Business {self.name!r} ({self.city})>"
