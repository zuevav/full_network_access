from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date


class PaymentCreate(BaseModel):
    amount: float = Field(default=0, ge=0)
    currency: str = Field(default="RUB", max_length=3)
    valid_from: date
    valid_until: date
    notes: Optional[str] = None


class PaymentUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = Field(None, max_length=3)
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    status: Optional[str] = Field(None, pattern="^(paid|expired|cancelled)$")
    notes: Optional[str] = None


class PaymentResponse(BaseModel):
    id: int
    client_id: int
    amount: float
    currency: str
    paid_at: datetime
    valid_from: date
    valid_until: date
    status: str
    notes: Optional[str]

    model_config = {"from_attributes": True}


class PaymentHistoryResponse(BaseModel):
    payments: List[PaymentResponse]
    current_valid_until: Optional[date]
    status: str  # active / expiring / expired / none
    days_left: Optional[int]
