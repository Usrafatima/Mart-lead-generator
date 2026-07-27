from pydantic import BaseModel


class ClassificationResponse(BaseModel):
    order_method: str
    delivery_system: str
    automation_status: str
    lead_priority: str
    notes: str