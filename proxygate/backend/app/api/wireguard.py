"""
WireGuard VPN API endpoints.

Admin endpoints for managing WireGuard server and client configurations.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, CurrentAdmin
from app.models import Client, WireguardConfig, WireguardServerConfig
from app.services.wireguard_manager import WireGuardManager, WgClient, WgServerSettings


router = APIRouter()
wg_manager = WireGuardManager()


# === Schemas ===

class WireguardServerSetupRequest(BaseModel):
    listen_port: int = 51820
    server_ip: str = "10.10.0.1"
    subnet: str = "10.10.0.0/24"
    dns: str = "1.1.1.1,8.8.8.8"
    mtu: int = 1420
    wstunnel_enabled: bool = False
    wstunnel_port: int = 443
    wstunnel_path: str = "/ws"


class WireguardServerResponse(BaseModel):
    is_installed: bool
    is_running: bool
    is_enabled: bool
    listen_port: Optional[int] = None
    server_ip: Optional[str] = None
    subnet: Optional[str] = None
    public_key: Optional[str] = None
    wstunnel_enabled: bool = False
    wstunnel_port: Optional[int] = None
    wstunnel_path: Optional[str] = None


class WireguardClientResponse(BaseModel):
    public_key: str
    assigned_ip: str
    is_active: bool
    config: Optional[str] = None
    traffic_up: int = 0
    traffic_down: int = 0
    last_handshake: Optional[datetime] = None


# === Admin Endpoints ===

@router.get("/wireguard/status")
async def get_wireguard_status(
        admin: CurrentAdmin,
        db: DBSession
) -> WireguardServerResponse:
    """Get WireGuard server status."""
    is_installed = wg_manager.is_installed()
    is_running = wg_manager.is_running()

    result = await db.execute(select(WireguardServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if server_config:
        return WireguardServerResponse(
            is_installed=is_installed,
            is_running=is_running,
            is_enabled=server_config.is_enabled,
            listen_port=server_config.listen_port,
            server_ip=server_config.server_ip,
            subnet=server_config.subnet,
            public_key=server_config.public_key,
            wstunnel_enabled=server_config.wstunnel_enabled,
            wstunnel_port=server_config.wstunnel_port,
            wstunnel_path=server_config.wstunnel_path
        )

    return WireguardServerResponse(
        is_installed=is_installed,
        is_running=is_running,
        is_enabled=False
    )


@router.post("/wireguard/setup")
async def setup_wireguard_server(
        request: WireguardServerSetupRequest,
        admin: CurrentAdmin,
        db: DBSession
):
    """
    Setup or reconfigure WireGuard server.
    """
    result = await db.execute(select(WireguardServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if not wg_manager.is_installed():
        success = wg_manager.install()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to install WireGuard")

    if not server_config:
        private_key, public_key = wg_manager.generate_keypair()
        if not private_key or not public_key:
            raise HTTPException(status_code=500, detail="Failed to generate WireGuard keys")

        server_config = WireguardServerConfig(
            private_key=private_key,
            public_key=public_key,
            listen_port=request.listen_port,
            server_ip=request.server_ip,
            subnet=request.subnet,
            dns=request.dns,
            mtu=request.mtu,
            wstunnel_enabled=request.wstunnel_enabled,
            wstunnel_port=request.wstunnel_port,
            wstunnel_path=request.wstunnel_path,
            is_enabled=True
        )
        db.add(server_config)
    else:
        server_config.listen_port = request.listen_port
        server_config.server_ip = request.server_ip
        server_config.subnet = request.subnet
        server_config.dns = request.dns
        server_config.mtu = request.mtu
        server_config.wstunnel_enabled = request.wstunnel_enabled
        server_config.wstunnel_port = request.wstunnel_port
        server_config.wstunnel_path = request.wstunnel_path
        server_config.is_enabled = True

    await db.commit()
    await db.refresh(server_config)

    # Setup wstunnel if enabled
    if server_config.wstunnel_enabled:
        if not wg_manager.install_wstunnel():
            # Don't fail, just warn
            pass
        wg_manager.setup_wstunnel(
            server_config.wstunnel_port,
            server_config.listen_port,
            server_config.wstunnel_path
        )

    # Write config and start
    await _reload_wireguard_config(db, server_config)
    wg_manager.enable_on_boot()

    if not wg_manager.start():
        raise HTTPException(status_code=500, detail="Failed to start WireGuard")

    return {
        "status": "success",
        "message": "WireGuard server configured and started",
        "public_key": server_config.public_key
    }


@router.post("/wireguard/stop")
async def stop_wireguard_server(
        admin: CurrentAdmin,
        db: DBSession
):
    """Stop WireGuard server."""
    result = await db.execute(select(WireguardServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if server_config:
        server_config.is_enabled = False
        await db.commit()

    wg_manager.stop()
    return {"status": "success", "message": "WireGuard server stopped"}


@router.post("/wireguard/start")
async def start_wireguard_server(
        admin: CurrentAdmin,
        db: DBSession
):
    """Start WireGuard server."""
    result = await db.execute(select(WireguardServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if not server_config:
        raise HTTPException(status_code=400, detail="WireGuard not configured")

    server_config.is_enabled = True
    await db.commit()

    if not wg_manager.start():
        raise HTTPException(status_code=500, detail="Failed to start WireGuard")

    return {"status": "success", "message": "WireGuard server started"}


@router.get("/{client_id}/wireguard")
async def get_client_wireguard_config(
        client_id: int,
        admin: CurrentAdmin,
        db: DBSession
) -> WireguardClientResponse:
    """Get WireGuard configuration for a client."""
    result = await db.execute(
        select(Client).where(Client.id == client_id).options(selectinload(Client.wireguard_config))
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    server_result = await db.execute(select(WireguardServerConfig).limit(1))
    server_config = server_result.scalar_one_or_none()

    if client.wireguard_config:
        config_text = None
        if server_config:
            server_ip = wg_manager.get_server_ip()
            server_settings = WgServerSettings(
                private_key=server_config.private_key,
                public_key=server_config.public_key,
                interface=server_config.interface,
                listen_port=server_config.listen_port,
                server_ip=server_config.server_ip,
                subnet=server_config.subnet,
                dns=server_config.dns,
                mtu=server_config.mtu,
                wstunnel_enabled=server_config.wstunnel_enabled,
                wstunnel_port=server_config.wstunnel_port,
                wstunnel_path=server_config.wstunnel_path
            )
            config_text = wg_manager.generate_client_config(
                server_ip,
                server_settings,
                client.wireguard_config.private_key,
                client.wireguard_config.assigned_ip,
                client.wireguard_config.preshared_key
            )

        return WireguardClientResponse(
            public_key=client.wireguard_config.public_key,
            assigned_ip=client.wireguard_config.assigned_ip,
            is_active=client.wireguard_config.is_active,
            config=config_text,
            traffic_up=client.wireguard_config.traffic_up,
            traffic_down=client.wireguard_config.traffic_down,
            last_handshake=client.wireguard_config.last_handshake
        )

    raise HTTPException(status_code=404, detail="WireGuard not configured for this client")


@router.post("/{client_id}/wireguard/enable")
async def enable_client_wireguard(
        client_id: int,
        admin: CurrentAdmin,
        db: DBSession
):
    """Enable WireGuard for a client."""
    result = await db.execute(
        select(Client).where(Client.id == client_id).options(selectinload(Client.wireguard_config))
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    server_result = await db.execute(select(WireguardServerConfig).limit(1))
    server_config = server_result.scalar_one_or_none()

    if not server_config:
        raise HTTPException(status_code=400, detail="WireGuard server not configured")

    if not client.wireguard_config:
        # Generate keys
        private_key, public_key = wg_manager.generate_keypair()
        if not private_key or not public_key:
            raise HTTPException(status_code=500, detail="Failed to generate keys")

        preshared_key = wg_manager.generate_preshared_key()

        # Get next available IP
        existing_result = await db.execute(
            select(WireguardConfig.assigned_ip).where(WireguardConfig.is_active == True)
        )
        used_ips = [row[0] for row in existing_result.all()]
        assigned_ip = wg_manager.get_next_available_ip(server_config.subnet, used_ips)

        if not assigned_ip:
            raise HTTPException(status_code=500, detail="No available IPs in pool")

        wg_config = WireguardConfig(
            client_id=client.id,
            private_key=private_key,
            public_key=public_key,
            preshared_key=preshared_key,
            assigned_ip=assigned_ip,
            is_active=True
        )
        db.add(wg_config)
    else:
        client.wireguard_config.is_active = True

    await db.commit()

    # Reload WireGuard config
    await _reload_wireguard_config(db, server_config)

    return {"status": "success", "message": "WireGuard enabled for client"}


@router.post("/{client_id}/wireguard/disable")
async def disable_client_wireguard(
        client_id: int,
        admin: CurrentAdmin,
        db: DBSession
):
    """Disable WireGuard for a client."""
    result = await db.execute(
        select(Client).where(Client.id == client_id).options(selectinload(Client.wireguard_config))
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.wireguard_config:
        client.wireguard_config.is_active = False
        await db.commit()

        server_result = await db.execute(select(WireguardServerConfig).limit(1))
        server_config = server_result.scalar_one_or_none()
        if server_config:
            await _reload_wireguard_config(db, server_config)

    return {"status": "success", "message": "WireGuard disabled for client"}


@router.post("/{client_id}/wireguard/regenerate")
async def regenerate_client_wireguard_keys(
        client_id: int,
        admin: CurrentAdmin,
        db: DBSession
):
    """Regenerate WireGuard keys for a client."""
    result = await db.execute(
        select(Client).where(Client.id == client_id).options(selectinload(Client.wireguard_config))
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.wireguard_config:
        raise HTTPException(status_code=404, detail="WireGuard not configured")

    private_key, public_key = wg_manager.generate_keypair()
    if not private_key or not public_key:
        raise HTTPException(status_code=500, detail="Failed to generate keys")

    client.wireguard_config.private_key = private_key
    client.wireguard_config.public_key = public_key
    client.wireguard_config.preshared_key = wg_manager.generate_preshared_key()

    await db.commit()

    server_result = await db.execute(select(WireguardServerConfig).limit(1))
    server_config = server_result.scalar_one_or_none()
    if server_config:
        await _reload_wireguard_config(db, server_config)

    return {"status": "success", "public_key": public_key}


async def _reload_wireguard_config(db: AsyncSession, server_config: WireguardServerConfig):
    """Helper to reload WireGuard config with all active clients."""
    clients_result = await db.execute(
        select(WireguardConfig).where(WireguardConfig.is_active == True)
    )
    wg_configs = clients_result.scalars().all()

    clients = [
        WgClient(
            public_key=c.public_key,
            preshared_key=c.preshared_key,
            assigned_ip=c.assigned_ip,
            is_active=c.is_active
        )
        for c in wg_configs
    ]

    server_settings = WgServerSettings(
        private_key=server_config.private_key,
        public_key=server_config.public_key,
        interface=server_config.interface,
        listen_port=server_config.listen_port,
        server_ip=server_config.server_ip,
        subnet=server_config.subnet,
        dns=server_config.dns,
        mtu=server_config.mtu,
        wstunnel_enabled=server_config.wstunnel_enabled,
        wstunnel_port=server_config.wstunnel_port,
        wstunnel_path=server_config.wstunnel_path
    )

    wg_manager.write_server_config(server_settings, clients)
    wg_manager.reload()
