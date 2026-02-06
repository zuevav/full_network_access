from fastapi import APIRouter

from app.api import auth, clients, domains, templates, payments, dashboard, vpn, proxy, profiles
from app.api import portal_auth, portal_profile, portal_domains, portal_account
from app.api import domain_requests, public, security, updates, ssl, system
from app.api import xray, portal_xray, wireguard, portal_wireguard

api_router = APIRouter()

# Admin API routes
api_router.include_router(auth.router, prefix="/admin/auth", tags=["Admin Auth"])
api_router.include_router(clients.router, prefix="/admin/clients", tags=["Admin Clients"])
api_router.include_router(domains.router, prefix="/admin/clients", tags=["Admin Domains"])
api_router.include_router(vpn.router, prefix="/admin/clients", tags=["Admin VPN"])
api_router.include_router(proxy.router, prefix="/admin/clients", tags=["Admin Proxy"])
api_router.include_router(profiles.router, prefix="/admin/clients", tags=["Admin Profiles"])
api_router.include_router(payments.router, prefix="/admin", tags=["Admin Payments"])
api_router.include_router(templates.router, prefix="/admin/templates", tags=["Admin Templates"])
api_router.include_router(dashboard.router, prefix="/admin/dashboard", tags=["Admin Dashboard"])
api_router.include_router(domain_requests.router, prefix="/admin/domain-requests", tags=["Admin Domain Requests"])
api_router.include_router(security.router, prefix="/admin", tags=["Admin Security"])
api_router.include_router(updates.router, prefix="/admin/updates", tags=["Admin Updates"])
api_router.include_router(ssl.router, prefix="/admin/ssl", tags=["Admin SSL"])
api_router.include_router(system.router, prefix="/admin/system", tags=["Admin System"])
api_router.include_router(xray.router, prefix="/admin/clients", tags=["Admin XRay"])
api_router.include_router(wireguard.router, prefix="/admin/clients", tags=["Admin WireGuard"])

# Client Portal API routes
api_router.include_router(portal_auth.router, prefix="/portal/auth", tags=["Portal Auth"])
api_router.include_router(portal_profile.router, prefix="/portal/profiles", tags=["Portal Profiles"])
api_router.include_router(portal_domains.router, prefix="/portal/domains", tags=["Portal Domains"])
api_router.include_router(portal_account.router, prefix="/portal", tags=["Portal Account"])
api_router.include_router(portal_xray.router, prefix="/portal/profiles", tags=["Portal XRay"])
api_router.include_router(portal_wireguard.router, prefix="/portal/profiles", tags=["Portal WireGuard"])

# Public routes
api_router.include_router(public.router, tags=["Public"])
