import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class BusinessCreate(BaseModel):
    """Payload the Google Maps Discovery Bot sends for each new business found."""
    name: str
    city: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    source_bot: str = "google_maps_bot"


class BusinessContactEnrich(BaseModel):
    """Payload the Website Scraper Bot sends to enrich an existing business."""
    business_id: uuid.UUID
    email: Optional[str] = None
    contact_page_url: Optional[str] = None


class BusinessSocialEnrich(BaseModel):
    """Payload the Social Media Scraper Bot sends to enrich an existing business."""
    business_id: uuid.UUID
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    whatsapp_number: Optional[str] = None
    linkedin_url: Optional[str] = None


class BusinessOut(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    rating: Optional[float] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    whatsapp_number: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_duplicate: bool
    created_at: datetime

    class Config:
        from_attributes = True
