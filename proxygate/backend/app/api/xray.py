"""
XRay VLESS + REALITY API endpoints.

Admin endpoints for managing XRay server and client configurations.
Portal endpoints for clients to get their connection info.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.api.auth import get_current_admin
from app.models import Client, XrayConfig, XrayServerConfig
from app.services.xray_manager import XRayManager, XrayClient, XrayServerSettings


router = APIRouter()
xray_manager = XRayManager()


# === Schemas ===

class XrayServerSetupRequest(BaseModel):
    port: int = 443
    dest_server: str = "www.microsoft.com"
    dest_port: int = 443
    server_name: str = "www.microsoft.com"


class XrayServerResponse(BaseModel):
    is_installed: bool
    is_running: bool
    is_enabled: bool
    port: Optional[int] = None
    server_name: Optional[str] = None
    public_key: Optional[str] = None
    short_id: Optional[str] = None


class XrayClientResponse(BaseModel):
    uuid: str
    short_id: Optional[str]
    is_active: bool
    vless_url: Optional[str] = None


class XrayConnectionInfo(BaseModel):
    server_ip: str
    port: int
    uuid: str
    flow: str
    security: str
    sni: str
    fingerprint: str
    public_key: str
    short_id: str
    vless_url: str
    apps: dict


# === Admin Endpoints ===

@router.get("/xray/status")
async def get_xray_status(
        admin=Depends(get_current_admin),
        db: AsyncSession = Depends(get_db)
) -> XrayServerResponse:
    """Get XRay server status."""
    is_installed = xray_manager.is_installed()
    is_running = xray_manager.is_running()

    # Get server config from DB
    result = await db.execute(select(XrayServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if server_config:
        return XrayServerResponse(
            is_installed=is_installed,
            is_running=is_running,
            is_enabled=server_config.is_enabled,
            port=server_config.port,
            server_name=server_config.server_name,
            public_key=server_config.public_key,
            short_id=server_config.short_id
        )

    return XrayServerResponse(
        is_installed=is_installed,
        is_running=is_running,
        is_enabled=False
    )


@router.post("/xray/setup")
async def setup_xray_server(
        request: XrayServerSetupRequest,
        admin=Depends(get_current_admin),
        db: AsyncSession = Depends(get_db)
):
    """
    Setup or reconfigure XRay server.

    This will:
    1. Install XRay if not already installed
    2. Generate REALITY keys
    3. Configure the server
    4. Start the service
    """
    # Check if already configured
    result = await db.execute(select(XrayServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if not xray_manager.is_installed():
        # Install XRay
        success = xray_manager.install()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to install XRay")

    # Generate new keys if not configured
    if not server_config:
        private_key, public_key = xray_manager.generate_keys()
        if not private_key or not public_key:
            raise HTTPException(status_code=500, detail="Failed to generate REALITY keys")

        short_id = xray_manager.generate_short_id()

        server_config = XrayServerConfig(
            port=request.port,
            private_key=private_key,
            public_key=public_key,
            short_id=short_id,
            dest_server=request.dest_server,
            dest_port=request.dest_port,
            server_name=request.server_name,
            is_enabled=True
        )
        db.add(server_config)
    else:
        # Update existing config
        server_config.port = request.port
        server_config.dest_server = request.dest_server
        server_config.dest_port = request.dest_port
        server_config.server_name = request.server_name
        server_config.is_enabled = True

    await db.commit()
    await db.refresh(server_config)

    # Get all XRay clients
    clients_result = await db.execute(
        select(XrayConfig).where(XrayConfig.is_active == True)
    )
    xray_configs = clients_result.scalars().all()

    clients = [
        XrayClient(uuid=c.uuid, short_id=c.short_id, is_active=c.is_active)
        for c in xray_configs
    ]

    server_settings = XrayServerSettings(
        port=server_config.port,
        private_key=server_config.private_key,
        public_key=server_config.public_key,
        short_id=server_config.short_id,
        dest_server=server_config.dest_server,
        dest_port=server_config.dest_port,
        server_name=server_config.server_name
    )

    # Write config and start
    xray_manager.write_config(server_settings, clients)
    xray_manager.enable()

    if not xray_manager.reload():
        raise HTTPException(status_code=500, detail="Failed to start XRay")

    return {
        "status": "success",
        "message": "XRay server configured and started",
        "public_key": server_config.public_key,
        "short_id": server_config.short_id
    }


@router.post("/xray/stop")
async def stop_xray_server(
        admin=Depends(get_current_admin),
        db: AsyncSession = Depends(get_db)
):
    """Stop XRay server."""
    result = await db.execute(select(XrayServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if server_config:
        server_config.is_enabled = False
        await db.commit()

    xray_manager.stop()
    return {"status": "success", "message": "XRay server stopped"}


@router.post("/xray/start")
async def start_xray_server(
        admin=Depends(get_current_admin),
        db: AsyncSession = Depends(get_db)
):
    """Start XRay server."""
    result = await db.execute(select(XrayServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if not server_config:
        raise HTTPException(status_code=400, detail="XRay not configured. Run setup first.")

    server_config.is_enabled = True
    await db.commit()

    if not xray_manager.start():
        raise HTTPException(status_code=500, detail="Failed to start XRay")

    return {"status": "success", "message": "XRay server started"}


@router.get("/{client_id}/xray")
async def get_client_xray_config(
        client_id: int,
        admin=Depends(get_current_admin),
        db: AsyncSession = Depends(get_db)
) -> XrayClientResponse:
    """Get XRay configuration for a client."""
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get server config
    server_result = await db.execute(select(XrayServerConfig).limit(1))
    server_config = server_result.scalar_one_or_none()

    if client.xray_config:
        vless_url = None
        if server_config:
            server_ip = xray_manager.get_server_ip()
            server_settings = XrayServerSettings(
                port=server_config.port,
                private_key=server_config.private_key,
                public_key=server_config.public_key,
                short_id=server_config.short_id,
                dest_server=server_config.dest_server,
                dest_port=server_config.dest_port,
                server_name=server_config.server_name
            )
            vless_url = xray_manager.generate_vless_url(
                server_ip,
                server_settings,
                client.xray_config.uuid,
                client.xray_config.short_id,
                client.name
            )

        return XrayClientResponse(
            uuid=client.xray_config.uuid,
            short_id=client.xray_config.short_id,
            is_active=client.xray_config.is_active,
            vless_url=vless_url
        )

    raise HTTPException(status_code=404, detail="XRay not configured for this client")


@router.post("/{client_id}/xray/enable")
async def enable_client_xray(
        client_id: int,
        admin=Depends(get_current_admin),
        db: AsyncSession = Depends(get_db)
):
    """Enable XRay for a client. Creates config if not exists."""
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get server config
    server_result = await db.execute(select(XrayServerConfig).limit(1))
    server_config = server_result.scalar_one_or_none()

    if not server_config:
        raise HTTPException(status_code=400, detail="XRay server not configured")

    if not client.xray_config:
        # Create new XRay config
        xray_config = XrayConfig(
            client_id=client.id,
            uuid=xray_manager.generate_uuid(),
            is_active=True
        )
        db.add(xray_config)
    else:
        client.xray_config.is_active = True

    await db.commit()

    # Reload XRay config
    await _reload_xray_config(db, server_config)

    return {"status": "success", "message": "XRay enabled for client"}


@router.post("/{client_id}/xray/disable")
async def disable_client_xray(
        client_id: int,
        admin=Depends(get_current_admin),
        db: AsyncSession = Depends(get_db)
):
    """Disable XRay for a client."""
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.xray_config:
        client.xray_config.is_active = False
        await db.commit()

        # Reload XRay config
        server_result = await db.execute(select(XrayServerConfig).limit(1))
        server_config = server_result.scalar_one_or_none()
        if server_config:
            await _reload_xray_config(db, server_config)

    return {"status": "success", "message": "XRay disabled for client"}


@router.post("/{client_id}/xray/regenerate")
async def regenerate_client_xray_uuid(
        client_id: int,
        admin=Depends(get_current_admin),
        db: AsyncSession = Depends(get_db)
):
    """Regenerate XRay UUID for a client (invalidates old connections)."""
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.xray_config:
        raise HTTPException(status_code=404, detail="XRay not configured for this client")

    client.xray_config.uuid = xray_manager.generate_uuid()
    await db.commit()

    # Reload XRay config
    server_result = await db.execute(select(XrayServerConfig).limit(1))
    server_config = server_result.scalar_one_or_none()
    if server_config:
        await _reload_xray_config(db, server_config)

    return {"status": "success", "uuid": client.xray_config.uuid}


async def _reload_xray_config(db: AsyncSession, server_config: XrayServerConfig):
    """Helper to reload XRay config with all active clients."""
    clients_result = await db.execute(
        select(XrayConfig).where(XrayConfig.is_active == True)
    )
    xray_configs = clients_result.scalars().all()

    clients = [
        XrayClient(uuid=c.uuid, short_id=c.short_id, is_active=c.is_active)
        for c in xray_configs
    ]

    server_settings = XrayServerSettings(
        port=server_config.port,
        private_key=server_config.private_key,
        public_key=server_config.public_key,
        short_id=server_config.short_id,
        dest_server=server_config.dest_server,
        dest_port=server_config.dest_port,
        server_name=server_config.server_name
    )

    xray_manager.write_config(server_settings, clients)
    xray_manager.reload()
