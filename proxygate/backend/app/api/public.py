from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession
from app.models import Client
from app.services.profile_generator import ProfileGenerator
from app.api.system import get_configured_domain, get_configured_ports


router = APIRouter()
profile_generator = ProfileGenerator()


@router.get("/connect/{access_token}", response_class=HTMLResponse)
async def client_connect_page(
    access_token: str,
    db: DBSession
):
    """Public client connection page (no auth required)."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.proxy_account),
            selectinload(Client.payments)
        )
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Not found")

    # Get subscription status
    valid_until_str = "Не оплачено"
    status_emoji = "🔴"
    if client.payments:
        latest = max(client.payments, key=lambda p: p.valid_until)
        valid_until_str = latest.valid_until.strftime("%d.%m.%Y")
        from datetime import date
        if latest.valid_until >= date.today():
            status_emoji = "🟢"

    # Get proxy settings - use domain if configured
    domain = get_configured_domain()
    proxy_host = domain if domain and domain != "localhost" else "127.0.0.1"
    http_port, _ = get_configured_ports()

    html = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZETIT FNA</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 480px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .logo {{ font-size: 32px; margin-bottom: 8px; }}
        h1 {{ font-size: 24px; color: #333; }}
        .subtitle {{ font-size: 12px; color: #888; margin-top: 4px; }}
        .status {{
            background: #f5f5f5;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .status-text {{ font-size: 18px; color: #333; }}
        .portal-btn {{
            display: block;
            width: 100%;
            padding: 14px;
            background: #667eea;
            color: white;
            text-align: center;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin-bottom: 24px;
        }}
        .portal-btn:hover {{ background: #5a6fd6; }}
        .section-title {{
            font-size: 14px;
            color: #888;
            margin-bottom: 12px;
            text-transform: uppercase;
        }}
        .download-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 24px;
        }}
        .download-btn {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 16px;
            background: #f5f5f5;
            border-radius: 12px;
            text-decoration: none;
            color: #333;
        }}
        .download-btn:hover {{ background: #e8e8e8; }}
        .download-icon {{ font-size: 24px; margin-bottom: 8px; }}
        .proxy-info {{
            background: #f5f5f5;
            border-radius: 12px;
            padding: 16px;
            font-size: 14px;
        }}
        .proxy-info p {{ margin-bottom: 8px; }}
        .proxy-info code {{
            background: #e0e0e0;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .footer {{
            text-align: center;
            margin-top: 24px;
            color: #888;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🔐</div>
            <h1>ZETIT FNA</h1>
            <div class="subtitle">Full Network Access</div>
        </div>

        <div class="status">
            <div class="status-text">
                Привет, <strong>{client.name}</strong>!<br>
                {status_emoji} Активен до: {valid_until_str}
            </div>
        </div>

        <a href="/my/link/{access_token}" class="portal-btn">🔑 Личный кабинет</a>

        <div class="section-title">Быстрое скачивание</div>
        <div class="download-grid">
            <a href="/api/download/{access_token}/ios" class="download-btn">
                <span class="download-icon">📱</span>
                <span>iPhone</span>
            </a>
            <a href="/api/download/{access_token}/android" class="download-btn">
                <span class="download-icon">🤖</span>
                <span>Android</span>
            </a>
            <a href="/api/download/{access_token}/windows" class="download-btn">
                <span class="download-icon">🪟</span>
                <span>Windows</span>
            </a>
            <a href="/api/download/{access_token}/macos" class="download-btn">
                <span class="download-icon">🍏</span>
                <span>macOS</span>
            </a>
        </div>

        {"" if not client.proxy_account else f'''
        <div class="section-title">Прокси</div>
        <div class="proxy-info">
            <p>Адрес: <code>{proxy_host}:{http_port}</code></p>
            <p>Логин: <code>{client.proxy_account.username}</code></p>
            <p>Пароль: <code>{client.proxy_account.password_plain}</code></p>
            <p><a href="/api/download/{access_token}/pac">⬇ Скачать PAC-файл</a></p>
        </div>
        '''}

        <div class="footer">
            Вопросы? Обратитесь к администратору
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)


@router.get("/download/{access_token}/windows")
async def download_windows_public(
    access_token: str,
    db: DBSession
):
    """Download Windows profile by access token."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None or client.vpn_config is None:
        raise HTTPException(status_code=404, detail="Not found")

    content = profile_generator.generate_windows_ps1(client)

    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}.ps1"'
        }
    )


@router.get("/download/{access_token}/ios")
async def download_ios_public(
    access_token: str,
    db: DBSession
):
    """Download iOS profile by access token."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None or client.vpn_config is None:
        raise HTTPException(status_code=404, detail="Not found")

    content = profile_generator.generate_ios_mobileconfig(client)

    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}.mobileconfig"'
        }
    )


@router.get("/download/{access_token}/macos")
async def download_macos_public(
    access_token: str,
    db: DBSession
):
    """Download macOS profile by access token."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None or client.vpn_config is None:
        raise HTTPException(status_code=404, detail="Not found")

    content = profile_generator.generate_macos_mobileconfig(client)

    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}-macos.mobileconfig"'
        }
    )


@router.get("/download/{access_token}/android")
async def download_android_public(
    access_token: str,
    db: DBSession
):
    """Download Android profile by access token."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None or client.vpn_config is None:
        raise HTTPException(status_code=404, detail="Not found")

    content = profile_generator.generate_android_sswan(client)

    return Response(
        content=content,
        media_type="application/vnd.strongswan.profile",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}.sswan"'
        }
    )


@router.get("/download/{access_token}/pac")
async def download_pac_public(
    access_token: str,
    db: DBSession
):
    """Download PAC file by access token."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.domains))
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Not found")

    content = profile_generator.generate_pac_file(client)

    return Response(
        content=content,
        media_type="application/x-ns-proxy-autoconfig",
        headers={
            "Content-Disposition": 'attachment; filename="zetit-fna.pac"'
        }
    )


@router.get("/pac/{access_token}")
async def get_pac_file(
    access_token: str,
    db: DBSession
):
    """Get PAC file for proxy auto-configuration."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.domains))
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Not found")

    content = profile_generator.generate_pac_file(client)

    return Response(
        content=content,
        media_type="application/x-ns-proxy-autoconfig"
    )
