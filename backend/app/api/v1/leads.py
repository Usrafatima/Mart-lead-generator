import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user, verify_internal_api_key
from app.models.business import Business
from app.models.lead import Lead, LeadPriority
from app.schemas.lead import LeadClassifyInput, LeadOut, LeadUpdate

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.post("/{business_id}/classify", response_model=LeadOut, dependencies=[Depends(verify_internal_api_key)])
def classify_lead(business_id: uuid.UUID, payload: LeadClassifyInput, db: Session = Depends(get_db)):
    """
    Called by the AI Classification Service once it has analyzed a business.
    Creates the Lead if it doesn't exist yet, otherwise updates it.
    """
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    lead = db.query(Lead).filter(Lead.business_id == business_id).first()
    if not lead:
        lead = Lead(business_id=business_id)
        db.add(lead)

    for field, value in payload.model_dump().items():
        setattr(lead, field, value)

    db.commit()
    db.refresh(lead)
    return lead


@router.get("", response_model=List[LeadOut])
def list_leads(
    priority: Optional[LeadPriority] = None,
    city: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Used by the Next.js frontend to display the leads table/dashboard."""
    query = db.query(Lead).join(Business)

    if priority:
        query = query.filter(Lead.priority == priority)
    if city:
        query = query.filter(Business.city.ilike(f"%{city}%"))

    return query.order_by(Lead.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: uuid.UUID, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Lets owner/team members manually override priority, status, or notes."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)

    db.commit()
    db.refresh(lead)
    return lead
