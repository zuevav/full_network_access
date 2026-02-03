from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import json

from app.api.deps import DBSession, CurrentClient
from app.models import Client, DomainRequest, DomainTemplate
from app.schemas.portal import (
    PortalDomainsResponse, DomainItem, DomainRequestCreate, DomainRequestResponse
)
from app.utils.helpers import normalize_domain


router = APIRouter()


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
