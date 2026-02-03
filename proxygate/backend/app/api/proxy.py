from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, CurrentAdmin
from app.models import Client, ProxyAccount
from app.schemas.proxy import ProxyCredentialsResponse
from app.utils.security import generate_password, get_password_hash
from app.config import settings


router = APIRouter()


@router.get("/{client_id}/proxy/credentials", response_model=ProxyCredentialsResponse)
async def get_proxy_credentials(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Get proxy credentials for a client."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.proxy_account))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.proxy_account is None:
        raise HTTPException(status_code=404, detail="Proxy not configured for this client")

    return ProxyCredentialsResponse(
        username=client.proxy_account.username,
        password=client.proxy_account.password_plain,
        http_host=settings.vps_public_ip,
        http_port=settings.proxy_http_port,
        socks_host=settings.vps_public_ip,
        socks_port=settings.proxy_socks_port,
        pac_url=f"https://{settings.vps_domain}/pac/{client.access_token}"
    )


@router.post("/{client_id}/proxy/reset-password", response_model=ProxyCredentialsResponse)
async def reset_proxy_password(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Reset proxy password for a client."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.proxy_account))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.proxy_account is None:
        raise HTTPException(status_code=404, detail="Proxy not configured for this client")

    new_password = generate_password()
    client.proxy_account.password_plain = new_password
    client.proxy_account.password_hash = get_password_hash(new_password)

    await db.commit()

    return ProxyCredentialsResponse(
        username=client.proxy_account.username,
        password=new_password,
        http_host=settings.vps_public_ip,
        http_port=settings.proxy_http_port,
        socks_host=settings.vps_public_ip,
        socks_port=settings.proxy_socks_port,
        pac_url=f"https://{settings.vps_domain}/pac/{client.access_token}"
    )


@router.get("/{client_id}/proxy/pac")
async def get_pac_file(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Get PAC file for a client (redirect to public URL)."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    return {"pac_url": f"https://{settings.vps_domain}/pac/{client.access_token}"}
