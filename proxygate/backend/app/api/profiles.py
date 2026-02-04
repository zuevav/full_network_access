from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, CurrentAdmin
from app.models import Client
from app.services.profile_generator import ProfileGenerator


router = APIRouter()
profile_generator = ProfileGenerator()


@router.get("/{client_id}/profiles/windows")
async def download_windows_profile(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Download Windows PowerShell script for a client."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.vpn_config is None:
        raise HTTPException(status_code=400, detail="VPN not configured for this client")

    content = profile_generator.generate_windows_ps1(client)

    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}.ps1"'
        }
    )


@router.get("/{client_id}/profiles/ios")
async def download_ios_profile(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Download iOS .mobileconfig for a client."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.vpn_config is None:
        raise HTTPException(status_code=400, detail="VPN not configured for this client")

    content = profile_generator.generate_ios_mobileconfig(client)

    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}.mobileconfig"'
        }
    )


@router.get("/{client_id}/profiles/macos")
async def download_macos_profile(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Download macOS .mobileconfig for a client."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.vpn_config is None:
        raise HTTPException(status_code=400, detail="VPN not configured for this client")

    content = profile_generator.generate_macos_mobileconfig(client)

    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}-macos.mobileconfig"'
        }
    )


@router.get("/{client_id}/profiles/android")
async def download_android_profile(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Download Android .sswan profile for a client."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.vpn_config is None:
        raise HTTPException(status_code=400, detail="VPN not configured for this client")

    content = profile_generator.generate_android_sswan(client)

    return Response(
        content=content,
        media_type="application/vnd.strongswan.profile",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}.sswan"'
        }
    )
