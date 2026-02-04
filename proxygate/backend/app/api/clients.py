from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from datetime import date

from app.api.deps import DBSession, CurrentAdmin
from app.models import Client, VpnConfig, ProxyAccount, ClientDomain, Payment
from app.schemas.client import (
    ClientCreate, ClientUpdate, ClientResponse, ClientListResponse,
    ClientListItem, ClientDetailResponse, DomainBrief, VpnConfigBrief, ProxyAccountBrief
)
from app.utils.security import generate_password, generate_access_token, get_password_hash
from app.utils.helpers import generate_username, get_subscription_status


router = APIRouter()


@router.get("", response_model=ClientListResponse)
async def list_clients(
    db: DBSession,
    admin: CurrentAdmin,
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    service_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    """List all clients with pagination and filters."""
    query = select(Client).options(
        selectinload(Client.domains),
        selectinload(Client.payments)
    )

    # Apply filters
    if search:
        query = query.where(
            or_(
                Client.name.ilike(f"%{search}%"),
                Client.email.ilike(f"%{search}%"),
                Client.phone.ilike(f"%{search}%")
            )
        )

    if status_filter == "active":
        query = query.where(Client.is_active == True)
    elif status_filter == "inactive":
        query = query.where(Client.is_active == False)

    if service_type:
        query = query.where(Client.service_type == service_type)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Pagination
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(Client.created_at.desc())

    result = await db.execute(query)
    clients = result.scalars().all()

    items = []
    for client in clients:
        # Get latest payment valid_until
        valid_until = None
        if client.payments:
            latest_payment = max(client.payments, key=lambda p: p.valid_until)
            valid_until = latest_payment.valid_until

        items.append(ClientListItem(
            id=client.id,
            name=client.name,
            email=client.email,
            service_type=client.service_type,
            is_active=client.is_active,
            domains_count=len([d for d in client.domains if d.is_active]),
            valid_until=valid_until,
            created_at=client.created_at
        ))

    pages = (total + per_page - 1) // per_page

    return ClientListResponse(
        items=items,
        total=total,
        page=page,
        pages=pages
    )


@router.post("", response_model=ClientDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    request: ClientCreate,
    db: DBSession,
    admin: CurrentAdmin
):
    """Create a new client."""
    # Create client
    access_token = generate_access_token()
    password = generate_password()

    client = Client(
        name=request.name,
        email=request.email,
        phone=request.phone,
        telegram_id=request.telegram_id,
        service_type=request.service_type,
        notes=request.notes,
        access_token=access_token,
        portal_password_hash=get_password_hash(password)
    )

    db.add(client)
    await db.flush()  # Get client ID

    # Get existing usernames for uniqueness check
    vpn_usernames = await db.execute(select(VpnConfig.username))
    proxy_usernames = await db.execute(select(ProxyAccount.username))
    existing_usernames = set(u for (u,) in vpn_usernames) | set(u for (u,) in proxy_usernames)

    # Generate username from client name
    username = generate_username(client.id, request.name, existing_usernames)

    # Create VPN config if needed
    if request.service_type in ("vpn", "both"):
        vpn_config = VpnConfig(
            client_id=client.id,
            username=username,
            password=password,
            is_active=True
        )
        db.add(vpn_config)

    # Create Proxy account if needed
    if request.service_type in ("proxy", "both"):
        proxy_account = ProxyAccount(
            client_id=client.id,
            username=username,
            password_hash=get_password_hash(password),
            password_plain=password,
            is_active=True
        )
        db.add(proxy_account)

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.proxy_account),
            selectinload(Client.domains),
            selectinload(Client.payments)
        )
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    return _client_to_detail_response(client)


@router.get("/{client_id}", response_model=ClientDetailResponse)
async def get_client(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Get client details."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.proxy_account),
            selectinload(Client.domains),
            selectinload(Client.payments)
        )
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    return _client_to_detail_response(client)


@router.put("/{client_id}", response_model=ClientDetailResponse)
async def update_client(
    client_id: int,
    request: ClientUpdate,
    db: DBSession,
    admin: CurrentAdmin
):
    """Update client details."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.proxy_account),
            selectinload(Client.domains),
            selectinload(Client.payments)
        )
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)

    await db.commit()
    await db.refresh(client)

    return _client_to_detail_response(client)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Delete a client."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    await db.delete(client)
    await db.commit()


@router.post("/{client_id}/activate", response_model=ClientDetailResponse)
async def activate_client(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Activate a client."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.proxy_account),
            selectinload(Client.domains),
            selectinload(Client.payments)
        )
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    client.is_active = True
    if client.vpn_config:
        client.vpn_config.is_active = True
    if client.proxy_account:
        client.proxy_account.is_active = True

    await db.commit()
    await db.refresh(client)

    return _client_to_detail_response(client)


@router.post("/{client_id}/deactivate", response_model=ClientDetailResponse)
async def deactivate_client(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Deactivate a client."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.proxy_account),
            selectinload(Client.domains),
            selectinload(Client.payments)
        )
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    client.is_active = False
    if client.vpn_config:
        client.vpn_config.is_active = False
    if client.proxy_account:
        client.proxy_account.is_active = False

    await db.commit()
    await db.refresh(client)

    return _client_to_detail_response(client)


def _client_to_detail_response(client: Client) -> ClientDetailResponse:
    """Convert Client model to ClientDetailResponse."""
    valid_until = None
    if client.payments:
        latest_payment = max(client.payments, key=lambda p: p.valid_until)
        valid_until = latest_payment.valid_until

    sub_status, _ = get_subscription_status(valid_until)

    domains = [
        DomainBrief(
            id=d.id,
            domain=d.domain,
            include_subdomains=d.include_subdomains,
            is_active=d.is_active,
            added_at=d.added_at
        )
        for d in client.domains
    ]

    return ClientDetailResponse(
        id=client.id,
        name=client.name,
        email=client.email,
        phone=client.phone,
        telegram_id=client.telegram_id,
        service_type=client.service_type,
        is_active=client.is_active,
        access_token=client.access_token,
        notes=client.notes,
        created_at=client.created_at,
        updated_at=client.updated_at,
        vpn_config=VpnConfigBrief(
            username=client.vpn_config.username,
            is_active=client.vpn_config.is_active
        ) if client.vpn_config else None,
        proxy_account=ProxyAccountBrief(
            username=client.proxy_account.username,
            is_active=client.proxy_account.is_active
        ) if client.proxy_account else None,
        domains=domains,
        domains_count=len([d for d in domains if d.is_active]),
        valid_until=valid_until,
        subscription_status=sub_status
    )
