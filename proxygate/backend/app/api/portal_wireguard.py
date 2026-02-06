"""
Portal WireGuard API endpoints.

Endpoints for clients to get their WireGuard configuration.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.api.portal_auth import get_current_client
from app.models import Client, WireguardConfig, WireguardServerConfig
from app.services.wireguard_manager import WireGuardManager, WgServerSettings


router = APIRouter()
wg_manager = WireGuardManager()


class WireguardConnectionResponse(BaseModel):
    available: bool
    server_ip: str = None
    server_port: int = None
    server_public_key: str = None
    client_ip: str = None
    dns: str = None
    wstunnel_enabled: bool = False
    config: str = None
    instructions: dict = None


@router.get("/wireguard")
async def get_wireguard_connection_info(
        client: Client = Depends(get_current_client),
        db: AsyncSession = Depends(get_db)
) -> WireguardConnectionResponse:
    """
    Get WireGuard connection information for the current client.
    """
    if not client.wireguard_config or not client.wireguard_config.is_active:
        return WireguardConnectionResponse(
            available=False,
            instructions={
                "message": "WireGuard не активирован для вашего аккаунта. Обратитесь к администратору."
            }
        )

    result = await db.execute(select(WireguardServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if not server_config or not server_config.is_enabled:
        return WireguardConnectionResponse(
            available=False,
            instructions={
                "message": "WireGuard сервер не настроен. Обратитесь к администратору."
            }
        )

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

    instructions = {
        "ios": {
            "app": "WireGuard",
            "app_store": "https://apps.apple.com/app/wireguard/id1441195209",
            "price": "Бесплатно",
            "steps": [
                "Установите WireGuard из App Store",
                "Откройте приложение",
                "Нажмите + → Create from QR code или Create from file",
                "Отсканируйте QR-код или импортируйте файл конфигурации",
                "Включите туннель"
            ]
        },
        "android": {
            "app": "WireGuard",
            "play_store": "https://play.google.com/store/apps/details?id=com.wireguard.android",
            "price": "Бесплатно",
            "steps": [
                "Установите WireGuard из Google Play",
                "Откройте приложение",
                "Нажмите + → Scan from QR code или Import from file",
                "Отсканируйте QR-код или выберите файл",
                "Включите туннель"
            ]
        },
        "windows": {
            "app": "WireGuard",
            "download": "https://www.wireguard.com/install/",
            "price": "Бесплатно",
            "steps": [
                "Скачайте WireGuard с официального сайта",
                "Установите приложение",
                "Откройте и нажмите 'Import tunnel(s) from file'",
                "Выберите скачанный .conf файл",
                "Нажмите 'Activate' для подключения"
            ]
        },
        "mac": {
            "app": "WireGuard",
            "app_store": "https://apps.apple.com/app/wireguard/id1451685025",
            "price": "Бесплатно",
            "steps": [
                "Установите WireGuard из Mac App Store",
                "Откройте приложение",
                "Нажмите + → Import tunnel(s) from file",
                "Выберите скачанный .conf файл",
                "Нажмите 'Activate' для подключения"
            ]
        },
        "linux": {
            "app": "wireguard-tools",
            "install": "sudo apt install wireguard-tools",
            "steps": [
                "Установите wireguard-tools",
                "Сохраните конфигурацию в /etc/wireguard/wg0.conf",
                "Запустите: sudo wg-quick up wg0",
                "Для автозапуска: sudo systemctl enable wg-quick@wg0"
            ]
        }
    }

    return WireguardConnectionResponse(
        available=True,
        server_ip=server_ip,
        server_port=server_config.wstunnel_port if server_config.wstunnel_enabled else server_config.listen_port,
        server_public_key=server_config.public_key,
        client_ip=client.wireguard_config.assigned_ip,
        dns=server_config.dns,
        wstunnel_enabled=server_config.wstunnel_enabled,
        config=config_text,
        instructions=instructions
    )


@router.get("/wireguard/config")
async def download_wireguard_config(
        client: Client = Depends(get_current_client),
        db: AsyncSession = Depends(get_db)
):
    """
    Download WireGuard configuration file.
    """
    if not client.wireguard_config or not client.wireguard_config.is_active:
        raise HTTPException(status_code=404, detail="WireGuard not enabled")

    result = await db.execute(select(WireguardServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if not server_config or not server_config.is_enabled:
        raise HTTPException(status_code=404, detail="WireGuard server not configured")

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

    # Return as downloadable file
    return PlainTextResponse(
        content=config_text,
        media_type="application/x-wireguard-config",
        headers={
            "Content-Disposition": f'attachment; filename="proxygate-{client.name}.conf"'
        }
    )


@router.get("/wireguard/qrcode")
async def get_wireguard_qrcode(
        client: Client = Depends(get_current_client),
        db: AsyncSession = Depends(get_db)
):
    """
    Get QR code for WireGuard configuration.
    """
    import base64
    import io

    try:
        import qrcode
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="QR code generation not available"
        )

    if not client.wireguard_config or not client.wireguard_config.is_active:
        raise HTTPException(status_code=404, detail="WireGuard not enabled")

    result = await db.execute(select(WireguardServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if not server_config or not server_config.is_enabled:
        raise HTTPException(status_code=404, detail="WireGuard server not configured")

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

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(config_text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return {
        "qrcode": f"data:image/png;base64,{img_base64}"
    }
