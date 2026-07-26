"""
Pydantic schemas for Business leads.

These mirror `app.bots.google_maps.BusinessLead` so the DB / API layer can
validate and serialize scraped data consistently. Other scrapers (website,
social media) can extend `BusinessBase` with their own optional fields.
"""

from typing import Optional

from pydantic import BaseModel, Field


class BusinessBase(BaseModel):
    name: str
    category: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    google_rating: Optional[float] = Field(default=None, ge=0, le=5)
    reviews_count: Optional[int] = Field(default=None, ge=0)
    maps_url: Optional[str] = None
    place_id: Optional[str] = None
    source: str = "google_maps"


class BusinessCreate(BusinessBase):
    """Used when inserting a newly scraped business into the database."""
    pass


class BusinessResponse(BusinessBase):
    """Used when returning a business record from the API."""
    id: int

    class Config:
        from_attributes = True
