"""
Security schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FailedLoginResponse(BaseModel):
    id: int
    ip_address: str
    username: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: str
    attempt_time: datetime

    class Config:
        from_attributes = True


class BlockedIPResponse(BaseModel):
    id: int
    ip_address: str
    reason: str
    failed_attempts: int
    blocked_at: datetime
    blocked_until: Optional[datetime] = None
    is_permanent: bool
    is_active: bool
    unblocked_at: Optional[datetime] = None
    unblocked_by: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class BlockedIPCreate(BaseModel):
    ip_address: str = Field(..., min_length=7, max_length=45)
    reason: str = Field(..., min_length=1, max_length=255)
    is_permanent: bool = True
    duration_minutes: Optional[int] = Field(None, ge=1, le=525600)  # max 1 year


class UnblockIPRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500)


class SecurityEventResponse(BaseModel):
    id: int
    event_type: str
    ip_address: Optional[str] = None
    username: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SecurityStatsResponse(BaseModel):
    active_blocks: int
    total_blocks: int
    failed_attempts_24h: int
    blocked_today: int
    events_today: int


class BlockedIPListResponse(BaseModel):
    items: list[BlockedIPResponse]
    total: int
    page: int
    per_page: int
