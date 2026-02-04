from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, date


class SubscriptionInfo(BaseModel):
    status: str  # active / expiring / expired / none
    valid_until: Optional[date]
    days_left: Optional[int]


class PortalMeResponse(BaseModel):
    name: str
    username: str
    is_active: bool
    service_type: str
    subscription: SubscriptionInfo
    domains_count: int
    pending_requests: int


class DomainItem(BaseModel):
    domain: str
    include_subdomains: bool
    added_at: datetime

    model_config = {"from_attributes": True}


class PortalDomainsResponse(BaseModel):
    domains: List[DomainItem]
    grouped_by_template: Dict[str, List[str]]


class DomainRequestCreate(BaseModel):
    domain: str = Field(..., min_length=1, max_length=255)
    reason: Optional[str] = Field(None, max_length=500)


class DomainRequestResponse(BaseModel):
    id: int
    domain: str
    reason: Optional[str]
    status: str
    admin_comment: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]

    model_config = {"from_attributes": True}


class PaymentHistoryItem(BaseModel):
    paid_at: datetime
    amount: float
    currency: str
    period: str  # "01.02 - 15.03.2026"

    model_config = {"from_attributes": True}


class PortalPaymentsResponse(BaseModel):
    current_subscription: SubscriptionInfo
    history: List[PaymentHistoryItem]


class VpnInfo(BaseModel):
    server: str
    username: str
    password: str


class ProxyInfo(BaseModel):
    host: str
    http_port: int
    socks_port: int
    username: str
    password: str


class PortalProfileInfoResponse(BaseModel):
    vpn: Optional[VpnInfo]
    proxy: Optional[ProxyInfo]
    pac_url: Optional[str]
    access_token: Optional[str]  # For public download links


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)
