import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.models.lead import OrderMethod, LeadPriority, AutomationStatus
from app.schemas.business import BusinessOut


class LeadClassifyInput(BaseModel):
    """Payload the AI Classification Service sends after analyzing a business."""
    order_method: OrderMethod = OrderMethod.unknown
    delivery_system: Optional[str] = None
    automation_status: AutomationStatus = AutomationStatus.not_started
    priority: LeadPriority = LeadPriority.medium
    notes: Optional[str] = None


class LeadOut(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    order_method: OrderMethod
    delivery_system: Optional[str] = None
    automation_status: AutomationStatus
    priority: LeadPriority
    notes: Optional[str] = None
    created_at: datetime
    business: Optional[BusinessOut] = None

    class Config:
        from_attributes = True


class LeadUpdate(BaseModel):
    """Used by the frontend (owner/member) to manually edit a lead."""
    priority: Optional[LeadPriority] = None
    automation_status: Optional[AutomationStatus] = None
    notes: Optional[str] = None
