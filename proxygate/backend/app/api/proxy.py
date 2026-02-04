from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, CurrentAdmin
from app.models import Client, ProxyAccount
from app.schemas.proxy import ProxyCredentialsResponse, ProxyAllowedIpsUpdate
from app.utils.security import generate_password, get_password_hash
from app.api.system import get_configured_domain, get_configured_ports


def get_proxy_host() -> str:
    """Get the host for proxy connections - domain if configured, otherwise IP."""
    domain = get_configured_domain()
    # If domain is set (not localhost or empty), use it
    if domain and domain != "localhost":
        return domain
    # Fallback to IP
    from app.api.system import get_configured_server_ip
    return get_configured_server_ip()


def parse_allowed_ips(allowed_ips_str: str | None) -> list[str] | None:
    """Parse comma-separated IP list into a list."""
    if not allowed_ips_str:
        return None
    return [ip.strip() for ip in allowed_ips_str.split(',') if ip.strip()]


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

    domain = get_configured_domain()
    proxy_host = get_proxy_host()
    http_port, socks_port = get_configured_ports()

    return ProxyCredentialsResponse(
        username=client.proxy_account.username,
        password=client.proxy_account.password_plain,
        http_host=proxy_host,
        http_port=http_port,
        socks_host=proxy_host,
        socks_port=socks_port,
        pac_url=f"https://{domain}/pac/{client.access_token}",
        allowed_ips=parse_allowed_ips(client.proxy_account.allowed_ips)
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

    domain = get_configured_domain()
    proxy_host = get_proxy_host()
    http_port, socks_port = get_configured_ports()

    return ProxyCredentialsResponse(
        username=client.proxy_account.username,
        password=new_password,
        http_host=proxy_host,
        http_port=http_port,
        socks_host=proxy_host,
        socks_port=socks_port,
        pac_url=f"https://{domain}/pac/{client.access_token}",
        allowed_ips=parse_allowed_ips(client.proxy_account.allowed_ips)
    )


@router.put("/{client_id}/proxy/allowed-ips")
async def update_allowed_ips(
    client_id: int,
    request: ProxyAllowedIpsUpdate,
    db: DBSession,
    admin: CurrentAdmin
):
    """Update allowed IPs for proxy (no auth required from these IPs)."""
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

    # Update allowed_ips via ORM
    allowed_ips_str = ','.join(request.allowed_ips) if request.allowed_ips else None
    client.proxy_account.allowed_ips = allowed_ips_str

    await db.commit()
    await db.refresh(client.proxy_account)

    return {"success": True, "allowed_ips": parse_allowed_ips(client.proxy_account.allowed_ips)}


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

    domain = get_configured_domain()
    return {"pac_url": f"https://{domain}/pac/{client.access_token}"}
