import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Text, Enum, Integer, Sequence
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class OrderMethod(str, enum.Enum):
    online = "online"
    phone = "phone"
    in_person = "in_person"
    unknown = "unknown"


class LeadPriority(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class AutomationStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"


class CallStatus(str, enum.Enum):
    """Outreach state, owned by whoever is calling the lead — not the bots."""

    not_contacted = "not_contacted"
    contacted = "contacted"
    no_answer = "no_answer"
    callback_scheduled = "callback_scheduled"
    interested = "interested"
    not_interested = "not_interested"


# Drives the human-readable Lead ID. A real Postgres sequence rather than a
# max(lead_ref)+1 query, so two Celery workers inserting at once can't collide.
lead_ref_seq = Sequence("lead_ref_seq", start=1)


class Lead(Base):
    """
    Created once a Business record has enough data to be classified by the
    AI Classification Service. One-to-one with Business.
    """

    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False, unique=True)

    # Short sequential number shown as "Lead ID" in the sheet. UUIDs are
    # unusable for humans reading a spreadsheet, and this doubles as the stable
    # key the Sheets export upserts rows on.
    lead_ref = Column(Integer, lead_ref_seq, unique=True, index=True, nullable=True)

    order_method = Column(Enum(OrderMethod), default=OrderMethod.unknown)
    # The team's sheet uses richer phrasing than the AI service's four-value
    # enum ("Walk-in + Delivery", "Website + Mobile"). Rather than widen the
    # enum and break the AI Classification Service's contract, we keep the
    # coarse enum for filtering and the original text for display/export.
    order_method_detail = Column(String, nullable=True)
    delivery_system = Column(String, nullable=True)
    automation_status = Column(Enum(AutomationStatus), default=AutomationStatus.not_started)
    # Same reasoning as order_method_detail: the sheet's Automation Status
    # describes how automated the *business* is ("Manual", "Semi Automated",
    # "Automated"), which doesn't map cleanly onto the enum's task-progress
    # wording. Kept verbatim for display and export.
    automation_status_detail = Column(String, nullable=True)
    priority = Column(Enum(LeadPriority), default=LeadPriority.medium)
    notes = Column(Text, nullable=True)

    # Manual outreach tracking columns from the team's sheet.
    call_status = Column(Enum(CallStatus), default=CallStatus.not_contacted, nullable=False)
    follow_up_date = Column(Date, nullable=True)
    # ISO week the lead was generated in, for the weekly-target report.
    week_number = Column(Integer, nullable=True, index=True)

    # Timestamp of the last successful export. Was named synced_to_sheets when
    # the plan was a Google Sheets API push; renamed when the team settled on
    # CSV files, since nothing syncs to Sheets any more.
    exported_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="lead")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Lead #{self.lead_ref} {self.priority}>"
