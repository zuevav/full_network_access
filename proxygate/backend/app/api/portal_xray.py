"""
Portal XRay API endpoints.

Endpoints for clients to get their XRay/VLESS connection info.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.api.portal_auth import get_current_client
from app.models import Client, XrayConfig, XrayServerConfig
from app.services.xray_manager import XRayManager, XrayServerSettings


router = APIRouter()
xray_manager = XRayManager()


class XrayConnectionResponse(BaseModel):
    available: bool
    server_ip: str = None
    port: int = None
    uuid: str = None
    flow: str = None
    security: str = None
    sni: str = None
    fingerprint: str = None
    public_key: str = None
    short_id: str = None
    vless_url: str = None
    instructions: dict = None


@router.get("/xray")
async def get_xray_connection_info(
        client: Client = Depends(get_current_client),
        db: AsyncSession = Depends(get_db)
) -> XrayConnectionResponse:
    """
    Get XRay/VLESS connection information for the current client.

    Returns all necessary info to configure a VLESS client:
    - Server address and port
    - UUID and authentication parameters
    - VLESS URL for easy import
    - Instructions for different platforms
    """
    # Check if client has XRay enabled
    if not client.xray_config or not client.xray_config.is_active:
        return XrayConnectionResponse(
            available=False,
            instructions={
                "message": "XRay/VLESS не активирован для вашего аккаунта. Обратитесь к администратору."
            }
        )

    # Get server config
    result = await db.execute(select(XrayServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if not server_config or not server_config.is_enabled:
        return XrayConnectionResponse(
            available=False,
            instructions={
                "message": "XRay сервер не настроен. Обратитесь к администратору."
            }
        )

    server_ip = xray_manager.get_server_ip()
    short_id = client.xray_config.short_id or server_config.short_id

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

    instructions = {
        "ios": {
            "app": "Shadowrocket",
            "app_store": "https://apps.apple.com/app/shadowrocket/id932747118",
            "price": "~$3",
            "steps": [
                "Установите Shadowrocket из App Store",
                "Откройте приложение",
                "Нажмите + в правом верхнем углу",
                "Выберите 'Scan QR Code' или 'Add from URL'",
                "Вставьте VLESS URL ниже",
                "Сохраните и включите VPN"
            ],
            "alternative_apps": ["Streisand", "V2Box"]
        },
        "android": {
            "app": "v2rayNG",
            "play_store": "https://play.google.com/store/apps/details?id=com.v2ray.ang",
            "github": "https://github.com/2dust/v2rayNG/releases",
            "steps": [
                "Установите v2rayNG из Google Play или GitHub",
                "Откройте приложение",
                "Нажмите + → Импорт из буфера обмена",
                "Скопируйте VLESS URL и вставьте",
                "Нажмите на созданную конфигурацию",
                "Нажмите кнопку V внизу для подключения"
            ],
            "alternative_apps": ["Matsuri", "NekoBox"]
        },
        "windows": {
            "app": "v2rayN",
            "github": "https://github.com/2dust/v2rayN/releases",
            "steps": [
                "Скачайте v2rayN с GitHub",
                "Распакуйте архив",
                "Запустите v2rayN.exe",
                "Клик правой кнопкой на иконке в трее → Импорт из буфера",
                "Скопируйте VLESS URL и вставьте",
                "Выберите сервер → Клик правой кнопкой → Установить как активный",
                "Включите системный прокси"
            ],
            "alternative_apps": ["Nekoray", "Qv2ray"]
        },
        "mac": {
            "app": "V2RayXS",
            "github": "https://github.com/tzmax/V2RayXS/releases",
            "steps": [
                "Скачайте V2RayXS с GitHub",
                "Установите приложение",
                "Откройте и нажмите Import → Paste from clipboard",
                "Скопируйте VLESS URL и вставьте",
                "Включите прокси"
            ],
            "alternative_apps": ["V2BOX", "Shadowrocket (Mac App Store)"]
        }
    }

    return XrayConnectionResponse(
        available=True,
        server_ip=server_ip,
        port=server_config.port,
        uuid=client.xray_config.uuid,
        flow="xtls-rprx-vision",
        security="reality",
        sni=server_config.server_name,
        fingerprint="chrome",
        public_key=server_config.public_key,
        short_id=short_id,
        vless_url=vless_url,
        instructions=instructions
    )


@router.get("/xray/qrcode")
async def get_xray_qrcode(
        client: Client = Depends(get_current_client),
        db: AsyncSession = Depends(get_db)
):
    """
    Get QR code for XRay/VLESS configuration.

    Returns a base64 encoded PNG image of the QR code.
    """
    import base64
    import io

    try:
        import qrcode
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="QR code generation not available. Install 'qrcode' package."
        )

    # Check if client has XRay enabled
    if not client.xray_config or not client.xray_config.is_active:
        raise HTTPException(status_code=404, detail="XRay not enabled for this client")

    # Get server config
    result = await db.execute(select(XrayServerConfig).limit(1))
    server_config = result.scalar_one_or_none()

    if not server_config or not server_config.is_enabled:
        raise HTTPException(status_code=404, detail="XRay server not configured")

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

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(vless_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return {
        "qrcode": f"data:image/png;base64,{img_base64}",
        "vless_url": vless_url
    }
