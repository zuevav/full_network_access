from fastapi import APIRouter
from sqlalchemy import select, func
from datetime import date, timedelta
from pydantic import BaseModel
from typing import List, Optional

from app.api.deps import DBSession, CurrentAdmin
from app.models import Client, ClientDomain, Payment, DomainRequest


router = APIRouter()


class ExpiringClient(BaseModel):
    id: int
    name: str
    valid_until: date
    days_left: int


class RecentClient(BaseModel):
    id: int
    name: str
    service_type: str
    created_at: str


class DashboardResponse(BaseModel):
    total_clients: int
    active_clients: int
    inactive_clients: int
    expiring_soon: List[ExpiringClient]
    expired: List[ExpiringClient]
    pending_domain_requests: int
    total_domains: int
    recent_clients: List[RecentClient]


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    db: DBSession,
    admin: CurrentAdmin
):
    """Get admin dashboard statistics."""
    today = date.today()
    week_later = today + timedelta(days=7)

    # Total clients
    total_result = await db.execute(select(func.count(Client.id)))
    total_clients = total_result.scalar() or 0

    # Active clients
    active_result = await db.execute(
        select(func.count(Client.id)).where(Client.is_active == True)
    )
    active_clients = active_result.scalar() or 0

    # Inactive clients
    inactive_clients = total_clients - active_clients

    # Total domains
    domains_result = await db.execute(
        select(func.count(ClientDomain.id)).where(ClientDomain.is_active == True)
    )
    total_domains = domains_result.scalar() or 0

    # Pending domain requests
    pending_result = await db.execute(
        select(func.count(DomainRequest.id)).where(DomainRequest.status == "pending")
    )
    pending_domain_requests = pending_result.scalar() or 0

    # Get all clients with payments for expiration analysis
    clients_result = await db.execute(
        select(Client, func.max(Payment.valid_until).label("max_valid"))
        .outerjoin(Payment)
        .group_by(Client.id)
    )
    clients_with_payments = clients_result.all()

    expiring_soon = []
    expired = []

    for client, max_valid in clients_with_payments:
        if max_valid is None:
            continue

        days_left = (max_valid - today).days

        client_info = ExpiringClient(
            id=client.id,
            name=client.name,
            valid_until=max_valid,
            days_left=days_left
        )

        if days_left < 0:
            expired.append(client_info)
        elif days_left <= 7:
            expiring_soon.append(client_info)

    # Sort by days_left
    expiring_soon.sort(key=lambda x: x.days_left)
    expired.sort(key=lambda x: x.days_left, reverse=True)

    # Recent clients (last 5)
    recent_result = await db.execute(
        select(Client).order_by(Client.created_at.desc()).limit(5)
    )
    recent = recent_result.scalars().all()

    recent_clients = [
        RecentClient(
            id=c.id,
            name=c.name,
            service_type=c.service_type,
            created_at=c.created_at.strftime("%d.%m.%Y")
        )
        for c in recent
    ]

    return DashboardResponse(
        total_clients=total_clients,
        active_clients=active_clients,
        inactive_clients=inactive_clients,
        expiring_soon=expiring_soon[:10],
        expired=expired[:10],
        pending_domain_requests=pending_domain_requests,
        total_domains=total_domains,
        recent_clients=recent_clients
    )
