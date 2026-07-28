import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.models.business import Business
from app.models.lead import Lead
from app.schemas.business import BusinessCreate, BusinessOut
from app.schemas.lead import LeadOut
from app.services.dedup import upsert_business
from app.services.lead_scoring import score_priority
from app.services.reports import current_week_number

router = APIRouter(prefix="/api/v1/businesses", tags=["businesses"])


def _first(values):
    if not values:
        return None
    return values[0] if isinstance(values, list) else values


def _copy_if_blank(target: Business, field: str, value) -> None:
    current = getattr(target, field, None)
    has_current = current is not None and (not isinstance(current, str) or current.strip())
    has_value = value is not None and (not isinstance(value, str) or str(value).strip())
    if not has_current and has_value:
        setattr(target, field, value)


def _ensure_lead(db: Session, business: Business) -> Lead:
    lead = db.query(Lead).filter(Lead.business_id == business.id).first()
    if lead is None:
        lead = Lead(business_id=business.id, week_number=current_week_number())
        db.add(lead)
        db.flush()
    return lead


@router.post("", response_model=BusinessOut)
def create_business(
    payload: BusinessCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Manual/dashboard entry point that uses the same dedup path as the bots."""
    business = Business(**payload.model_dump())
    business, _ = upsert_business(db, business, commit=True)
    return business


@router.get("", response_model=List[BusinessOut])
def list_businesses(
    city: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Used by the Next.js frontend to browse raw scraped businesses (before/without AI classification)."""
    query = db.query(Business)
    if city:
        query = query.filter(Business.city.ilike(f"%{city}%"))
    return query.order_by(Business.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{business_id}", response_model=BusinessOut)
def get_business(business_id: uuid.UUID, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


@router.post("/{business_id}/enrich-website", response_model=BusinessOut)
async def enrich_business_from_website(
    business_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Runs the website scraper for an existing business and stores useful contact
    and social fields on the same Business row.
    """
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    if not business.website:
        raise HTTPException(status_code=400, detail="Business has no website to scrape")

    from app.bots.website_scraper.scraper import WebsiteScraper

    result = await WebsiteScraper().scrape(business.website)
    if result.get("status") != "success":
        raise HTTPException(status_code=502, detail=result.get("error", "Website scrape failed"))

    social = result.get("social_links") or {}
    _copy_if_blank(business, "email", _first(result.get("emails")))
    _copy_if_blank(business, "phone", _first(result.get("phones")))
    _copy_if_blank(business, "address", result.get("address"))
    _copy_if_blank(business, "contact_page_url", result.get("contact_page"))
    _copy_if_blank(business, "facebook_url", social.get("facebook"))
    _copy_if_blank(business, "instagram_url", social.get("instagram"))
    _copy_if_blank(business, "linkedin_url", social.get("linkedin"))
    _copy_if_blank(business, "whatsapp_number", social.get("whatsapp"))
    business.set_derived_fields()

    db.commit()
    db.refresh(business)
    return business


@router.post("/{business_id}/score", response_model=LeadOut)
def score_business_as_lead(
    business_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Creates/updates the Lead using the deterministic fallback scorer. The
    external AI service can still overwrite richer classifications later.
    """
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    lead = _ensure_lead(db, business)
    lead.priority = score_priority(business)
    if not lead.notes:
        lead.notes = "Auto-scored from available website, email, phone and social signals."

    db.commit()
    db.refresh(lead)
    return lead
