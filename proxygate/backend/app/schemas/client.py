from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    telegram_id: Optional[str] = Field(None, max_length=100)
    service_type: str = Field(default="both", pattern="^(vpn|proxy|both)$")
    notes: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    telegram_id: Optional[str] = Field(None, max_length=100)
    service_type: Optional[str] = Field(None, pattern="^(vpn|proxy|both)$")
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class VpnConfigBrief(BaseModel):
    username: str
    is_active: bool

    model_config = {"from_attributes": True}


class ProxyAccountBrief(BaseModel):
    username: str
    is_active: bool

    model_config = {"from_attributes": True}


class PaymentBrief(BaseModel):
    id: int
    valid_until: datetime
    status: str

    model_config = {"from_attributes": True}


class ClientResponse(BaseModel):
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    telegram_id: Optional[str]
    service_type: str
    is_active: bool
    access_token: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClientListItem(BaseModel):
    id: int
    name: str
    email: Optional[str]
    service_type: str
    is_active: bool
    domains_count: int = 0
    valid_until: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClientListResponse(BaseModel):
    items: List[ClientListItem]
    total: int
    page: int
    pages: int


class DomainBrief(BaseModel):
    id: int
    domain: str
    include_subdomains: bool
    is_active: bool
    added_at: datetime

    model_config = {"from_attributes": True}


class ClientDetailResponse(BaseModel):
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    telegram_id: Optional[str]
    service_type: str
    is_active: bool
    access_token: str
    access_token_expires_at: Optional[datetime] = None
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    vpn_config: Optional[VpnConfigBrief]
    proxy_account: Optional[ProxyAccountBrief]
    domains: List[DomainBrief]
    domains_count: int
    valid_until: Optional[datetime]
    subscription_status: str  # active / expiring / expired / none

    model_config = {"from_attributes": True}
