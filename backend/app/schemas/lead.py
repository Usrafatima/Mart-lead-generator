import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

from app.models.lead import OrderMethod, LeadPriority, AutomationStatus, CallStatus
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
    lead_ref: Optional[int] = None
    order_method: OrderMethod
    order_method_detail: Optional[str] = None
    delivery_system: Optional[str] = None
    automation_status: AutomationStatus
    automation_status_detail: Optional[str] = None
    priority: LeadPriority
    notes: Optional[str] = None
    call_status: CallStatus
    follow_up_date: Optional[date] = None
    week_number: Optional[int] = None
    exported_at: Optional[datetime] = None
    created_at: datetime
    business: Optional[BusinessOut] = None

    class Config:
        from_attributes = True


class LeadUpdate(BaseModel):
    """Used by the frontend (owner/member) to manually edit a lead."""
    priority: Optional[LeadPriority] = None
    automation_status: Optional[AutomationStatus] = None
    call_status: Optional[CallStatus] = None
    follow_up_date: Optional[date] = None
    notes: Optional[str] = None
