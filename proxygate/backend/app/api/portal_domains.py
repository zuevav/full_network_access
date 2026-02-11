from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from typing import List, Optional
import json

from app.api.deps import DBSession, CurrentClient
from app.models import Client, ClientDomain, DomainRequest, DomainTemplate
from app.schemas.portal import (
    PortalDomainsResponse, DomainItem, DomainRequestCreate, DomainRequestResponse
)
from app.schemas.domain import DomainAnalyzeResponse
from app.api.domains import analyze_domain_resources, get_base_domain
from app.utils.helpers import normalize_domain
from app.services.proxy_manager import rebuild_proxy_config


router = APIRouter()


# --- Portal-specific schemas ---

class PortalTemplateItem(BaseModel):
    id: int
    name: str
    description: Optional[str]
    icon: Optional[str]
    domains: List[str]
    domains_count: int

class PortalApplyTemplateRequest(BaseModel):
    template_id: int

class PortalApplyTemplateResponse(BaseModel):
    added_count: int
    domains: List[str]

class PortalAddDomainsRequest(BaseModel):
    domains: List[str] = Field(..., min_length=1)
    include_subdomains: bool = True

class PortalAddDomainResponse(BaseModel):
    id: int
    domain: str
    include_subdomains: bool

    model_config = {"from_attributes": True}

class PortalAnalyzeRequest(BaseModel):
    domain: str = Field(..., min_length=1)


# --- Existing endpoints ---

@router.get("", response_model=PortalDomainsResponse)
async def get_my_domains(
    client: CurrentClient,
    db: DBSession
):
    """Get client's domains list."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.domains))
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    domains = [
        DomainItem(
            domain=d.domain,
            include_subdomains=d.include_subdomains,
            added_at=d.added_at
        )
        for d in client.domains if d.is_active
    ]

    # Group domains by template
    templates_result = await db.execute(select(DomainTemplate).where(DomainTemplate.is_active == True))
    templates = templates_result.scalars().all()

    client_domains_set = {d.domain for d in domains}
    grouped = {}

    for template in templates:
        template_domains = json.loads(template.domains_json)
        matching = [d for d in template_domains if d in client_domains_set]
        if matching:
            grouped[template.name] = matching
            client_domains_set -= set(matching)

    # Remaining domains go to "Other"
    if client_domains_set:
        grouped["Другое"] = list(client_domains_set)

    return PortalDomainsResponse(
        domains=domains,
        grouped_by_template=grouped
    )


@router.post("/request", response_model=DomainRequestResponse)
async def request_domain(
    request: DomainRequestCreate,
    client: CurrentClient,
    db: DBSession
):
    """Request a new domain to be added."""
    normalized = normalize_domain(request.domain)

    domain_request = DomainRequest(
        client_id=client.id,
        domain=normalized,
        reason=request.reason,
        status="pending"
    )

    db.add(domain_request)
    await db.commit()
    await db.refresh(domain_request)

    return DomainRequestResponse(
        id=domain_request.id,
        domain=domain_request.domain,
        reason=domain_request.reason,
        status=domain_request.status,
        admin_comment=None,
        created_at=domain_request.created_at,
        resolved_at=None
    )


@router.get("/requests", response_model=list[DomainRequestResponse])
async def get_my_domain_requests(
    client: CurrentClient,
    db: DBSession
):
    """Get client's domain requests history."""
    result = await db.execute(
        select(DomainRequest)
        .where(DomainRequest.client_id == client.id)
        .order_by(DomainRequest.created_at.desc())
    )
    requests = result.scalars().all()

    return [
        DomainRequestResponse(
            id=r.id,
            domain=r.domain,
            reason=r.reason,
            status=r.status,
            admin_comment=r.admin_comment,
            created_at=r.created_at,
            resolved_at=r.resolved_at
        )
        for r in requests
    ]


# --- New portal endpoints ---

@router.get("/templates", response_model=List[PortalTemplateItem])
async def get_public_templates(
    client: CurrentClient,
    db: DBSession
):
    """Get list of public domain templates available for self-service."""
    result = await db.execute(
        select(DomainTemplate)
        .where(DomainTemplate.is_active == True, DomainTemplate.is_public == True)
        .order_by(DomainTemplate.name)
    )
    templates = result.scalars().all()

    return [
        PortalTemplateItem(
            id=t.id,
            name=t.name,
            description=t.description,
            icon=t.icon,
            domains=json.loads(t.domains_json),
            domains_count=len(json.loads(t.domains_json))
        )
        for t in templates
    ]


@router.post("/apply-template", response_model=PortalApplyTemplateResponse)
async def apply_template(
    request: PortalApplyTemplateRequest,
    client: CurrentClient,
    db: DBSession
):
    """Apply a public template — adds template domains to client directly."""
    # Verify template is public and active
    result = await db.execute(
        select(DomainTemplate)
        .where(
            DomainTemplate.id == request.template_id,
            DomainTemplate.is_active == True,
            DomainTemplate.is_public == True
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found or not available")

    template_domains = json.loads(template.domains_json)

    # Get existing client domains
    result = await db.execute(
        select(ClientDomain).where(ClientDomain.client_id == client.id)
    )
    existing_domains = {d.domain for d in result.scalars().all()}

    added = []
    for domain in template_domains:
        normalized = normalize_domain(domain)
        if normalized and normalized not in existing_domains:
            client_domain = ClientDomain(
                client_id=client.id,
                domain=normalized,
                include_subdomains=True,
                is_active=True
            )
            db.add(client_domain)
            added.append(normalized)
            existing_domains.add(normalized)

    await db.commit()

    if added:
        await rebuild_proxy_config(db)

    return PortalApplyTemplateResponse(
        added_count=len(added),
        domains=added
    )


@router.post("/add", response_model=List[PortalAddDomainResponse])
async def add_domains(
    request: PortalAddDomainsRequest,
    client: CurrentClient,
    db: DBSession
):
    """Add custom domains directly (self-service, no approval needed)."""
    # Get existing client domains
    result = await db.execute(
        select(ClientDomain).where(ClientDomain.client_id == client.id)
    )
    existing_domains = {d.domain for d in result.scalars().all()}

    added = []
    for domain in request.domains:
        normalized = normalize_domain(domain)
        if normalized and normalized not in existing_domains:
            client_domain = ClientDomain(
                client_id=client.id,
                domain=normalized,
                include_subdomains=request.include_subdomains,
                is_active=True
            )
            db.add(client_domain)
            added.append(client_domain)
            existing_domains.add(normalized)

    await db.commit()

    if added:
        await rebuild_proxy_config(db)

    return [
        PortalAddDomainResponse(
            id=d.id,
            domain=d.domain,
            include_subdomains=d.include_subdomains
        )
        for d in added
    ]


@router.post("/analyze", response_model=DomainAnalyzeResponse)
async def analyze_domain(
    request: PortalAnalyzeRequest,
    client: CurrentClient
):
    """Analyze a domain to find related domains (redirects, CDNs, APIs)."""
    original = normalize_domain(request.domain)
    if not original:
        raise HTTPException(status_code=400, detail="Invalid domain")

    redirect_domains, resource_domains, error = await analyze_domain_resources(request.domain)

    all_suggested = redirect_domains | resource_domains

    common_skip = {
        'google-analytics.com', 'googletagmanager.com', 'doubleclick.net',
        'facebook.net', 'fbcdn.net', 'twitter.com', 'twimg.com',
        'addthis.com', 'sharethis.com', 'disqus.com'
    }

    suggested = sorted([d for d in all_suggested if get_base_domain(d) not in common_skip])

    return DomainAnalyzeResponse(
        original_domain=original,
        redirects=sorted(redirect_domains),
        resources=sorted(resource_domains - redirect_domains),
        suggested=suggested,
        error=error
    )
