import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.assignments import intern_for_city
from app.core.database import get_db
from app.deps import get_current_user
from app.models.business import Business
from app.schemas.business import BusinessOut
from app.services.discovery_ingest import ingest_scraped_leads

router = APIRouter(prefix="/api/v1/discovery", tags=["discovery"])


class DiscoveryRequest(BaseModel):
    category: str = Field(default="supermarket", min_length=2)
    city: str = Field(min_length=2)
    country: Optional[str] = None
    max_results: int = Field(default=10, ge=1, le=100)
    assigned_to: Optional[str] = None
    week_number: Optional[int] = Field(default=None, ge=1, le=53)
    headless: bool = True


class DiscoveryResponse(BaseModel):
    summary: dict
    assigned_to: Optional[str] = None
    businesses: list[BusinessOut]

    class Config:
        from_attributes = True


@router.post("/google-maps", response_model=DiscoveryResponse)
async def discover_google_maps(
    payload: DiscoveryRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Run the Google Maps bot, upsert results through the dedup module, and
    create unclassified Lead rows so the dashboard/reporting modules see them.
    """
    try:
        from app.bots.google_maps import GoogleMapsBot
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Google Maps bot dependencies are not installed: {exc}",
        ) from exc

    bot = GoogleMapsBot(headless=payload.headless)

    try:
        scraped = await bot.search_businesses(
            category=payload.category,
            city=payload.city,
            country=payload.country,
            max_results=payload.max_results,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google Maps discovery failed: {exc}") from exc

    owner = payload.assigned_to or intern_for_city(payload.city)
    summary = ingest_scraped_leads(
        db,
        scraped,
        assigned_to=owner,
        week_number=payload.week_number,
        commit=True,
    )

    business_ids = [item.id for item in scraped if isinstance(getattr(item, "id", None), uuid.UUID)]
    query = db.query(Business).filter(Business.city.ilike(payload.city))
    if business_ids:
        query = query.filter(Business.id.in_(business_ids))

    businesses = query.order_by(Business.created_at.desc()).limit(payload.max_results).all()
    return DiscoveryResponse(summary=summary, assigned_to=owner, businesses=businesses)


@router.get("/cities")
def discovery_cities(current_user=Depends(get_current_user)):
    """Assignment-aware city list for dashboard dropdowns."""
    from app.core.assignments import INTERNS

    return [
        {"city": city, "intern": intern.name, "country": intern.country}
        for intern in INTERNS
        for city in intern.cities
    ]
