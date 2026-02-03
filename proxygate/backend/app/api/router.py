from fastapi import APIRouter

from app.api import auth, clients, domains, templates, payments, dashboard, vpn, proxy, profiles
from app.api import portal_auth, portal_profile, portal_domains, portal_account
from app.api import domain_requests, public, security, updates

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

# Client Portal API routes
api_router.include_router(portal_auth.router, prefix="/portal/auth", tags=["Portal Auth"])
api_router.include_router(portal_profile.router, prefix="/portal/profiles", tags=["Portal Profiles"])
api_router.include_router(portal_domains.router, prefix="/portal/domains", tags=["Portal Domains"])
api_router.include_router(portal_account.router, prefix="/portal", tags=["Portal Account"])

# Public routes
api_router.include_router(public.router, tags=["Public"])
