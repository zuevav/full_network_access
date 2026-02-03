from app.schemas.client import (
    ClientCreate, ClientUpdate, ClientResponse, ClientListResponse, ClientDetailResponse
)
from app.schemas.domain import (
    DomainCreate, DomainResponse, DomainTemplateCreate, DomainTemplateUpdate, DomainTemplateResponse
)
from app.schemas.vpn import VpnConfigResponse, VpnCredentialsResponse
from app.schemas.proxy import ProxyAccountResponse, ProxyCredentialsResponse
from app.schemas.payment import PaymentCreate, PaymentUpdate, PaymentResponse
from app.schemas.portal import (
    PortalMeResponse, PortalDomainsResponse, PortalPaymentsResponse,
    PortalProfileInfoResponse, DomainRequestCreate, DomainRequestResponse,
    ChangePasswordRequest
)
from app.schemas.auth import (
    AdminLoginRequest, ClientLoginRequest, TokenResponse, AdminUserResponse
)

__all__ = [
    # Client
    "ClientCreate", "ClientUpdate", "ClientResponse", "ClientListResponse", "ClientDetailResponse",
    # Domain
    "DomainCreate", "DomainResponse", "DomainTemplateCreate", "DomainTemplateUpdate", "DomainTemplateResponse",
    # VPN
    "VpnConfigResponse", "VpnCredentialsResponse",
    # Proxy
    "ProxyAccountResponse", "ProxyCredentialsResponse",
    # Payment
    "PaymentCreate", "PaymentUpdate", "PaymentResponse",
    # Portal
    "PortalMeResponse", "PortalDomainsResponse", "PortalPaymentsResponse",
    "PortalProfileInfoResponse", "DomainRequestCreate", "DomainRequestResponse",
    "ChangePasswordRequest",
    # Auth
    "AdminLoginRequest", "ClientLoginRequest", "TokenResponse", "AdminUserResponse",
]
