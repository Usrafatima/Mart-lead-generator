from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String

from app.core.database import Base

class Lead(Base):

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)

    business_name = Column(String)

    category = Column(String)

    website = Column(String)

    phone = Column(String)

    city = Column(String)

    country = Column(String)

    order_method = Column(String)

    delivery_system = Column(String)

    automation_status = Column(String)

    lead_priority = Column(String)

    notes = Column(String)