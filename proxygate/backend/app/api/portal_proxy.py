from typing import List, Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, CurrentClient
from app.models import Client
from app.models.ip_whitelist import IpWhitelistLog
from app.middleware.security import get_client_ip
from app.services.proxy_manager import rebuild_proxy_config


router = APIRouter()


class IpWhitelistResponse(BaseModel):
    client_ip: str
    allowed_ips: List[str]
    ip_already_whitelisted: bool


class IpWhitelistActionResponse(BaseModel):
    success: bool
    ip: str
    message: Optional[str] = None


@router.get("/proxy/ip-whitelist", response_model=IpWhitelistResponse)
async def get_ip_whitelist(
    request: Request,
    client: CurrentClient,
    db: DBSession
):
    """Get client's IP whitelist and current IP."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.proxy_account))
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    client_ip = get_client_ip(request)
    allowed_ips = []
    if client.proxy_account and client.proxy_account.allowed_ips:
        allowed_ips = [ip.strip() for ip in client.proxy_account.allowed_ips.split(",") if ip.strip()]

    return IpWhitelistResponse(
        client_ip=client_ip,
        allowed_ips=allowed_ips,
        ip_already_whitelisted=client_ip in allowed_ips,
    )


@router.post("/proxy/ip-whitelist", response_model=IpWhitelistActionResponse)
async def add_ip_to_whitelist(
    request: Request,
    client: CurrentClient,
    db: DBSession
):
    """Add client's current IP to proxy whitelist."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.proxy_account))
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    if client.proxy_account is None:
        raise HTTPException(status_code=400, detail="Proxy not configured")

    ip = get_client_ip(request)

    existing_ips = []
    if client.proxy_account.allowed_ips:
        existing_ips = [i.strip() for i in client.proxy_account.allowed_ips.split(",") if i.strip()]

    if ip in existing_ips:
        return IpWhitelistActionResponse(success=True, ip=ip, message="already_added")

    existing_ips.append(ip)
    client.proxy_account.allowed_ips = ",".join(existing_ips)

    db.add(IpWhitelistLog(client_id=client.id, ip_address=ip, action="added"))
    await db.flush()

    await rebuild_proxy_config(db)

    return IpWhitelistActionResponse(success=True, ip=ip)


@router.delete("/proxy/ip-whitelist/{ip}", response_model=IpWhitelistActionResponse)
async def remove_ip_from_whitelist(
    ip: str,
    client: CurrentClient,
    db: DBSession
):
    """Remove IP from client's proxy whitelist."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.proxy_account))
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    if client.proxy_account is None:
        raise HTTPException(status_code=400, detail="Proxy not configured")

    existing_ips = []
    if client.proxy_account.allowed_ips:
        existing_ips = [i.strip() for i in client.proxy_account.allowed_ips.split(",") if i.strip()]

    if ip not in existing_ips:
        raise HTTPException(status_code=404, detail="IP not found in whitelist")

    existing_ips.remove(ip)
    client.proxy_account.allowed_ips = ",".join(existing_ips) if existing_ips else None

    db.add(IpWhitelistLog(client_id=client.id, ip_address=ip, action="removed"))
    await db.flush()

    await rebuild_proxy_config(db)

    return IpWhitelistActionResponse(success=True, ip=ip, message="removed")
