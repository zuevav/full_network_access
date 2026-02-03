from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.api.deps import DBSession, CurrentAdmin
from app.models import DomainRequest, ClientDomain, Client
from app.schemas.portal import DomainRequestResponse
from app.utils.helpers import normalize_domain


router = APIRouter()


class DomainRequestWithClient(DomainRequestResponse):
    client_name: str


@router.get("", response_model=list[DomainRequestWithClient])
async def list_domain_requests(
    db: DBSession,
    admin: CurrentAdmin,
    status: Optional[str] = Query(None, pattern="^(pending|approved|rejected)$")
):
    """List all domain requests."""
    query = select(DomainRequest).options(selectinload(DomainRequest.client))

    if status:
        query = query.where(DomainRequest.status == status)

    query = query.order_by(DomainRequest.created_at.desc())

    result = await db.execute(query)
    requests = result.scalars().all()

    return [
        DomainRequestWithClient(
            id=r.id,
            domain=r.domain,
            reason=r.reason,
            status=r.status,
            admin_comment=r.admin_comment,
            created_at=r.created_at,
            resolved_at=r.resolved_at,
            client_name=r.client.name
        )
        for r in requests
    ]


class ApproveRequest(DomainRequestResponse):
    admin_comment: Optional[str] = None


class RejectRequest(DomainRequestResponse):
    admin_comment: str


@router.put("/{request_id}/approve", response_model=DomainRequestResponse)
async def approve_domain_request(
    request_id: int,
    body: Optional[ApproveRequest] = None,
    db: DBSession = None,
    admin: CurrentAdmin = None
):
    """Approve a domain request."""
    result = await db.execute(
        select(DomainRequest)
        .options(selectinload(DomainRequest.client))
        .where(DomainRequest.id == request_id)
    )
    request = result.scalar_one_or_none()

    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Request already processed")

    # Add domain to client
    normalized = normalize_domain(request.domain)

    # Check if domain already exists
    existing = await db.execute(
        select(ClientDomain).where(
            ClientDomain.client_id == request.client_id,
            ClientDomain.domain == normalized
        )
    )
    if existing.scalar_one_or_none() is None:
        client_domain = ClientDomain(
            client_id=request.client_id,
            domain=normalized,
            include_subdomains=True,
            is_active=True
        )
        db.add(client_domain)

    # Update request
    request.status = "approved"
    request.resolved_at = datetime.utcnow()
    if body and body.admin_comment:
        request.admin_comment = body.admin_comment

    await db.commit()
    await db.refresh(request)

    return DomainRequestResponse(
        id=request.id,
        domain=request.domain,
        reason=request.reason,
        status=request.status,
        admin_comment=request.admin_comment,
        created_at=request.created_at,
        resolved_at=request.resolved_at
    )


@router.put("/{request_id}/reject", response_model=DomainRequestResponse)
async def reject_domain_request(
    request_id: int,
    body: RejectRequest,
    db: DBSession,
    admin: CurrentAdmin
):
    """Reject a domain request."""
    result = await db.execute(
        select(DomainRequest).where(DomainRequest.id == request_id)
    )
    request = result.scalar_one_or_none()

    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Request already processed")

    request.status = "rejected"
    request.resolved_at = datetime.utcnow()
    request.admin_comment = body.admin_comment

    await db.commit()
    await db.refresh(request)

    return DomainRequestResponse(
        id=request.id,
        domain=request.domain,
        reason=request.reason,
        status=request.status,
        admin_comment=request.admin_comment,
        created_at=request.created_at,
        resolved_at=request.resolved_at
    )
