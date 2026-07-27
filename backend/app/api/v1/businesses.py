import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.models.business import Business
from app.schemas.business import BusinessOut

router = APIRouter(prefix="/api/v1/businesses", tags=["businesses"])


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
