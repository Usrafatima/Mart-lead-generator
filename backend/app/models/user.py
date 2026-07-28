import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Enum
import enum

from app.core.database import Base, GUID


class UserRole(str, enum.Enum):
    owner = "owner"
    member = "member"


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.member, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
