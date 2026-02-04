from fastapi import APIRouter
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, CurrentClient
from app.models import Client
from app.schemas.portal import PortalProfileInfoResponse, VpnInfo, ProxyInfo
from app.services.profile_generator import ProfileGenerator
from app.api.system import get_configured_domain, get_configured_server_ip, get_configured_ports


router = APIRouter()
profile_generator = ProfileGenerator()


@router.get("/info", response_model=PortalProfileInfoResponse)
async def get_profile_info(
    client: CurrentClient,
    db: DBSession
):
    """Get all connection info for the client."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.proxy_account)
        )
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    # Get configured settings
    domain = get_configured_domain()
    server_ip = get_configured_server_ip()
    http_port, socks_port = get_configured_ports()

    vpn_info = None
    if client.vpn_config:
        vpn_info = VpnInfo(
            server=domain,
            username=client.vpn_config.username,
            password=client.vpn_config.password
        )

    proxy_info = None
    if client.proxy_account:
        proxy_info = ProxyInfo(
            host=server_ip,
            http_port=http_port,
            socks_port=socks_port,
            username=client.proxy_account.username,
            password=client.proxy_account.password_plain
        )

    pac_url = None
    if client.proxy_account:
        pac_url = f"https://{domain}/pac/{client.access_token}"

    return PortalProfileInfoResponse(
        vpn=vpn_info,
        proxy=proxy_info,
        pac_url=pac_url
    )


@router.get("/windows")
async def download_windows_profile(
    client: CurrentClient,
    db: DBSession
):
    """Download Windows PowerShell script."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    if client.vpn_config is None:
        return Response(content="VPN not configured", status_code=400)

    content = profile_generator.generate_windows_ps1(client)

    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}.ps1"'
        }
    )


@router.get("/ios")
async def download_ios_profile(
    client: CurrentClient,
    db: DBSession
):
    """Download iOS .mobileconfig."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    if client.vpn_config is None:
        return Response(content="VPN not configured", status_code=400)

    content = profile_generator.generate_ios_mobileconfig(client)

    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}.mobileconfig"'
        }
    )


@router.get("/macos")
async def download_macos_profile(
    client: CurrentClient,
    db: DBSession
):
    """Download macOS .mobileconfig."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    if client.vpn_config is None:
        return Response(content="VPN not configured", status_code=400)

    content = profile_generator.generate_macos_mobileconfig(client)

    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}-macos.mobileconfig"'
        }
    )


@router.get("/android")
async def download_android_profile(
    client: CurrentClient,
    db: DBSession
):
    """Download Android .sswan profile."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    if client.vpn_config is None:
        return Response(content="VPN not configured", status_code=400)

    content = profile_generator.generate_android_sswan(client)

    return Response(
        content=content,
        media_type="application/vnd.strongswan.profile",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}.sswan"'
        }
    )


@router.get("/pac")
async def download_pac_file(
    client: CurrentClient,
    db: DBSession
):
    """Download PAC file."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.domains))
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    content = profile_generator.generate_pac_file(client)

    return Response(
        content=content,
        media_type="application/x-ns-proxy-autoconfig",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna.pac"'
        }
    )
