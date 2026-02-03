from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import json

from app.api.deps import DBSession, CurrentAdmin
from app.models import Client, ClientDomain, DomainTemplate
from app.schemas.domain import DomainCreate, DomainResponse, ApplyTemplateRequest
from app.utils.helpers import normalize_domain


router = APIRouter()


@router.get("/{client_id}/domains", response_model=list[DomainResponse])
async def list_client_domains(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """List all domains for a client."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.domains))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    return [
        DomainResponse(
            id=d.id,
            domain=d.domain,
            include_subdomains=d.include_subdomains,
            is_active=d.is_active,
            added_at=d.added_at
        )
        for d in client.domains
    ]


@router.post("/{client_id}/domains", response_model=list[DomainResponse], status_code=status.HTTP_201_CREATED)
async def add_client_domains(
    client_id: int,
    request: DomainCreate,
    db: DBSession,
    admin: CurrentAdmin
):
    """Add domains to a client."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get existing domains
    result = await db.execute(
        select(ClientDomain).where(ClientDomain.client_id == client_id)
    )
    existing_domains = {d.domain for d in result.scalars().all()}

    added_domains = []
    for domain in request.domains:
        normalized = normalize_domain(domain)
        if normalized and normalized not in existing_domains:
            client_domain = ClientDomain(
                client_id=client_id,
                domain=normalized,
                include_subdomains=request.include_subdomains,
                is_active=True
            )
            db.add(client_domain)
            added_domains.append(client_domain)
            existing_domains.add(normalized)

    await db.commit()

    return [
        DomainResponse(
            id=d.id,
            domain=d.domain,
            include_subdomains=d.include_subdomains,
            is_active=d.is_active,
            added_at=d.added_at
        )
        for d in added_domains
    ]


@router.delete("/{client_id}/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client_domain(
    client_id: int,
    domain_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Delete a domain from a client."""
    result = await db.execute(
        select(ClientDomain)
        .where(ClientDomain.id == domain_id, ClientDomain.client_id == client_id)
    )
    domain = result.scalar_one_or_none()

    if domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")

    await db.delete(domain)
    await db.commit()


@router.post("/{client_id}/domains/template", response_model=list[DomainResponse])
async def apply_template(
    client_id: int,
    request: ApplyTemplateRequest,
    db: DBSession,
    admin: CurrentAdmin
):
    """Apply a domain template to a client."""
    # Check client exists
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get template
    result = await db.execute(
        select(DomainTemplate).where(DomainTemplate.id == request.template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    # Parse template domains
    template_domains = json.loads(template.domains_json)

    # Get existing domains
    result = await db.execute(
        select(ClientDomain).where(ClientDomain.client_id == client_id)
    )
    existing_domains = {d.domain for d in result.scalars().all()}

    added_domains = []
    for domain in template_domains:
        normalized = normalize_domain(domain)
        if normalized and normalized not in existing_domains:
            client_domain = ClientDomain(
                client_id=client_id,
                domain=normalized,
                include_subdomains=True,
                is_active=True
            )
            db.add(client_domain)
            added_domains.append(client_domain)
            existing_domains.add(normalized)

    await db.commit()

    return [
        DomainResponse(
            id=d.id,
            domain=d.domain,
            include_subdomains=d.include_subdomains,
            is_active=d.is_active,
            added_at=d.added_at
        )
        for d in added_domains
    ]


@router.post("/{client_id}/domains/sync", status_code=status.HTTP_200_OK)
async def sync_domains(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Sync/resolve domains to IP routes for a client."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.domains), selectinload(Client.vpn_config))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    # TODO: Implement domain resolver integration
    # For now, return success
    return {"message": "Domain routes synced", "domains_count": len(client.domains)}
