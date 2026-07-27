import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Business(Base):
    """
    Raw business record, primarily created by the Google Maps Discovery Bot.
    Website/Social scraper bots enrich this same record rather than creating
    a new one, which is what lets us de-duplicate leads later.
    """

    __tablename__ = "businesses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String, nullable=False, index=True)
    city = Column(String, index=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    website = Column(String, nullable=True)
    rating = Column(Float, nullable=True)

    # Filled in later by Website Scraper Bot
    email = Column(String, nullable=True)
    contact_page_url = Column(String, nullable=True)

    # Filled in later by Social Media Scraper Bot
    facebook_url = Column(String, nullable=True)
    instagram_url = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)

    is_duplicate = Column(Boolean, default=False)
    source_bot = Column(String, nullable=True)  # e.g. "google_maps_bot"

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead = relationship("Lead", back_populates="business", uselist=False)
