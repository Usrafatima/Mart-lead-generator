import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum
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


class Lead(Base):
    """
    Created once a Business record has enough data to be classified by the
    AI Classification Service. One-to-one with Business.
    """

    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False, unique=True)

    order_method = Column(Enum(OrderMethod), default=OrderMethod.unknown)
    delivery_system = Column(String, nullable=True)
    automation_status = Column(Enum(AutomationStatus), default=AutomationStatus.not_started)
    priority = Column(Enum(LeadPriority), default=LeadPriority.medium)
    notes = Column(Text, nullable=True)

    synced_to_sheets = Column(DateTime, nullable=True)  # timestamp of last successful export

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="lead")
