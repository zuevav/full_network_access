from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import json

from app.api.deps import DBSession, CurrentAdmin
from app.models import Client, VpnConfig
from app.schemas.vpn import VpnCredentialsResponse, VpnRoutesResponse
from app.utils.security import generate_password
from app.api.system import get_configured_domain


router = APIRouter()


@router.get("/{client_id}/vpn/credentials", response_model=VpnCredentialsResponse)
async def get_vpn_credentials(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Get VPN credentials for a client."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.vpn_config))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.vpn_config is None:
        raise HTTPException(status_code=404, detail="VPN not configured for this client")

    domain = get_configured_domain()
    return VpnCredentialsResponse(
        username=client.vpn_config.username,
        password=client.vpn_config.password,
        server=domain,
        server_id=domain
    )


@router.post("/{client_id}/vpn/reset-password", response_model=VpnCredentialsResponse)
async def reset_vpn_password(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Reset VPN password for a client."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.vpn_config))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.vpn_config is None:
        raise HTTPException(status_code=404, detail="VPN not configured for this client")

    new_password = generate_password()
    client.vpn_config.password = new_password

    await db.commit()

    domain = get_configured_domain()
    return VpnCredentialsResponse(
        username=client.vpn_config.username,
        password=new_password,
        server=domain,
        server_id=domain
    )


@router.get("/{client_id}/vpn/routes", response_model=VpnRoutesResponse)
async def get_vpn_routes(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Get VPN routes (CIDRs) for a client."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.vpn_config), selectinload(Client.domains))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.vpn_config is None:
        raise HTTPException(status_code=404, detail="VPN not configured for this client")

    routes = []
    if client.vpn_config.resolved_routes:
        routes = json.loads(client.vpn_config.resolved_routes)

    return VpnRoutesResponse(
        routes=routes,
        domains_count=len([d for d in client.domains if d.is_active]),
        last_resolved=client.vpn_config.last_resolved
    )
