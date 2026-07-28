import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class BusinessCreate(BaseModel):
    """Payload the Google Maps Discovery Bot sends for each new business found."""
    name: str
    city: str
    country: Optional[str] = None
    business_type: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    owner_manager_name: Optional[str] = None
    assigned_to: Optional[str] = None
    place_id: Optional[str] = None
    maps_url: Optional[str] = None
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
    business_type: Optional[str] = None
    country: Optional[str] = None
    city: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    website_available: bool
    email: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    owner_manager_name: Optional[str] = None
    contact_page_url: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    whatsapp_number: Optional[str] = None
    linkedin_url: Optional[str] = None
    place_id: Optional[str] = None
    maps_url: Optional[str] = None
    source_bot: Optional[str] = None
    assigned_to: Optional[str] = None
    is_duplicate: bool
    created_at: datetime

    class Config:
        from_attributes = True
