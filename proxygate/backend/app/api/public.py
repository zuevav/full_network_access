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
            border: none;
            cursor: pointer;
            font-family: inherit;
            font-size: inherit;
        }}
        .download-btn:hover {{ background: #e8e8e8; }}
        .download-icon {{ font-size: 24px; margin-bottom: 8px; }}
        /* Modal styles */
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }}
        .modal-overlay.active {{ display: flex; }}
        .modal {{
            background: white;
            border-radius: 16px;
            width: 100%;
            max-width: 400px;
            max-height: 90vh;
            overflow: auto;
        }}
        .modal-header {{
            padding: 16px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }}
        .modal-title {{ font-size: 18px; font-weight: 600; color: #333; }}
        .modal-subtitle {{ font-size: 14px; color: #888; margin-top: 4px; }}
        .modal-close {{
            background: none;
            border: none;
            font-size: 24px;
            color: #888;
            cursor: pointer;
            padding: 0;
            line-height: 1;
        }}
        .modal-body {{ padding: 16px; }}
        .modal-option {{
            display: block;
            padding: 16px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            margin-bottom: 12px;
            text-decoration: none;
            color: #333;
            position: relative;
        }}
        .modal-option:hover {{ border-color: #667eea; background: #f8f9ff; }}
        .modal-option-icon {{ font-size: 24px; margin-bottom: 8px; }}
        .modal-option-title {{ font-weight: 600; margin-bottom: 4px; }}
        .modal-option-desc {{ font-size: 13px; color: #666; }}
        .modal-badge {{
            position: absolute;
            top: -8px;
            right: 12px;
            background: #fbbf24;
            color: #78350f;
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 10px;
        }}
        .modal-footer {{
            padding: 12px 16px;
            background: #f5f5f5;
            border-radius: 0 0 16px 16px;
            text-align: center;
            font-size: 12px;
            color: #888;
        }}
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
            <button onclick="showModal()" class="download-btn">
                <span class="download-icon">📱</span>
                <span>iPhone</span>
            </button>
            <a href="/api/download/{access_token}/android" class="download-btn">
                <span class="download-icon">🤖</span>
                <span>Android</span>
            </a>
            <a href="/api/download/{access_token}/windows" class="download-btn">
                <span class="download-icon">🪟</span>
                <span>Windows</span>
            </a>
            <button onclick="showModal()" class="download-btn">
                <span class="download-icon">🍏</span>
                <span>macOS</span>
            </button>
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

    <!-- iOS/macOS VPN Mode Selection Modal -->
    <div id="vpnModal" class="modal-overlay" onclick="hideModal(event)">
        <div class="modal" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div>
                    <div class="modal-title">Выберите режим VPN</div>
                    <div class="modal-subtitle">Как должен работать VPN?</div>
                </div>
                <button class="modal-close" onclick="hideModal()">&times;</button>
            </div>
            <div class="modal-body">
                <a href="/api/download/{access_token}/ios?mode=ondemand" class="modal-option">
                    <span class="modal-badge">Рекомендуем</span>
                    <div class="modal-option-icon">⚡</div>
                    <div class="modal-option-title">Авто (по доменам)</div>
                    <div class="modal-option-desc">VPN включается только при открытии нужных сайтов.</div>
                </a>
                <a href="/api/download/{access_token}/ios?mode=always" class="modal-option">
                    <div class="modal-option-icon">🛡️</div>
                    <div class="modal-option-title">Всегда (Split-туннель)</div>
                    <div class="modal-option-desc">VPN всегда включён, но только рабочий трафик идёт через VPN.</div>
                </a>
                <a href="/api/download/{access_token}/ios?mode=full" class="modal-option">
                    <div class="modal-option-icon">🌐</div>
                    <div class="modal-option-title">Всегда (Весь трафик)</div>
                    <div class="modal-option-desc">Весь трафик через VPN. Максимальная защита.</div>
                </a>
            </div>
            <div class="modal-footer" style="background: #fff3cd; color: #856404;">
                <strong>📱 Инструкция для iPhone:</strong><br>
                1. Нажмите на режим выше<br>
                2. Разрешите загрузку профиля<br>
                3. Откройте: <strong>Настройки → Основные → VPN и управление устройством</strong><br>
                4. Нажмите на загруженный профиль → Установить
            </div>
        </div>
    </div>

    <script>
        function showModal() {{
            document.getElementById('vpnModal').classList.add('active');
        }}
        function hideModal(event) {{
            if (!event || event.target === event.currentTarget) {{
                document.getElementById('vpnModal').classList.remove('active');
            }}
        }}
    </script>
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
    db: DBSession,
    mode: str = "ondemand"
):
    """Download iOS profile by access token with VPN mode selection."""
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

    # Validate mode
    if mode not in ("ondemand", "always", "full"):
        mode = "ondemand"

    content = profile_generator.generate_ios_mobileconfig(client, mode=mode)
    mode_suffix = f"-{mode}" if mode != "ondemand" else ""

    # iOS Safari headers for proper download handling
    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}{mode_suffix}.mobileconfig"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff"
        }
    )


@router.get("/download/{access_token}/macos")
async def download_macos_public(
    access_token: str,
    db: DBSession,
    mode: str = "ondemand"
):
    """Download macOS profile by access token with VPN mode selection."""
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

    # Validate mode
    if mode not in ("ondemand", "always", "full"):
        mode = "ondemand"

    content = profile_generator.generate_macos_mobileconfig(client, mode=mode)
    mode_suffix = f"-{mode}" if mode != "ondemand" else ""

    # Safari headers for proper download handling
    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}-macos{mode_suffix}.mobileconfig"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff"
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


@router.get("/download/{access_token}/proxy-setup")
async def download_proxy_setup_public(
    access_token: str,
    db: DBSession
):
    """Download Windows proxy setup PowerShell script by access token."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.proxy_account))
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None or client.proxy_account is None:
        raise HTTPException(status_code=404, detail="Not found")

    domain = get_configured_domain()
    http_port, _ = get_configured_ports()
    pac_url = f"https://{domain}/pac/{client.access_token}"

    script = f'''# ZETIT FNA - Windows Proxy Setup Script
# Run as Administrator

param(
    [switch]$UsePAC,
    [switch]$UseManual,
    [switch]$Disable
)

$ErrorActionPreference = "Stop"

# Proxy settings
$ProxyServer = "{domain}:{http_port}"
$PacUrl = "{pac_url}"
$Username = "{client.proxy_account.username}"

Write-Host "ZETIT FNA - Proxy Setup" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host ""

if ($Disable) {{
    Write-Host "Disabling proxy..." -ForegroundColor Yellow

    # Disable proxy in registry
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyEnable -Value 0
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name AutoConfigURL -Value ""

    # Refresh Internet settings
    $signature = @"
[DllImport("wininet.dll", SetLastError = true, CharSet=CharSet.Auto)]
public static extern bool InternetSetOption(IntPtr hInternet, int dwOption, IntPtr lpBuffer, int dwBufferLength);
"@
    $type = Add-Type -MemberDefinition $signature -Name WinInet -Namespace Win32API -PassThru
    $INTERNET_OPTION_SETTINGS_CHANGED = 39
    $INTERNET_OPTION_REFRESH = 37
    [Win32API.WinInet]::InternetSetOption([IntPtr]::Zero, $INTERNET_OPTION_SETTINGS_CHANGED, [IntPtr]::Zero, 0) | Out-Null
    [Win32API.WinInet]::InternetSetOption([IntPtr]::Zero, $INTERNET_OPTION_REFRESH, [IntPtr]::Zero, 0) | Out-Null

    Write-Host "Proxy disabled successfully!" -ForegroundColor Green
    exit 0
}}

if ($UsePAC -or (-not $UseManual)) {{
    Write-Host "Configuring PAC (Automatic Configuration)..." -ForegroundColor Yellow
    Write-Host "PAC URL: $PacUrl" -ForegroundColor Gray

    # Set PAC URL
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name AutoConfigURL -Value $PacUrl
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyEnable -Value 0

    Write-Host ""
    Write-Host "PAC configured successfully!" -ForegroundColor Green
    Write-Host "Only sites from your domain list will use proxy." -ForegroundColor Gray
}}

if ($UseManual) {{
    Write-Host "Configuring manual proxy..." -ForegroundColor Yellow
    Write-Host "Proxy Server: $ProxyServer" -ForegroundColor Gray

    # Set manual proxy
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyServer -Value $ProxyServer
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyEnable -Value 1
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name AutoConfigURL -Value ""

    Write-Host ""
    Write-Host "Manual proxy configured!" -ForegroundColor Green
    Write-Host "ALL traffic will go through proxy." -ForegroundColor Yellow
}}

# Refresh Internet settings
$signature = @"
[DllImport("wininet.dll", SetLastError = true, CharSet=CharSet.Auto)]
public static extern bool InternetSetOption(IntPtr hInternet, int dwOption, IntPtr lpBuffer, int dwBufferLength);
"@
$type = Add-Type -MemberDefinition $signature -Name WinInet -Namespace Win32API -PassThru
$INTERNET_OPTION_SETTINGS_CHANGED = 39
$INTERNET_OPTION_REFRESH = 37
[Win32API.WinInet]::InternetSetOption([IntPtr]::Zero, $INTERNET_OPTION_SETTINGS_CHANGED, [IntPtr]::Zero, 0) | Out-Null
[Win32API.WinInet]::InternetSetOption([IntPtr]::Zero, $INTERNET_OPTION_REFRESH, [IntPtr]::Zero, 0) | Out-Null

Write-Host ""
Write-Host "Your credentials:" -ForegroundColor Cyan
Write-Host "  Username: $Username" -ForegroundColor White
Write-Host "  Password: (same as VPN)" -ForegroundColor White
Write-Host ""
Write-Host "Note: Browser will ask for credentials on first connection." -ForegroundColor Gray
Write-Host ""
Write-Host "Usage:" -ForegroundColor Cyan
Write-Host "  .\\proxy-setup.ps1           - Configure PAC (recommended)" -ForegroundColor Gray
Write-Host "  .\\proxy-setup.ps1 -UseManual - Configure manual proxy for ALL traffic" -ForegroundColor Gray
Write-Host "  .\\proxy-setup.ps1 -Disable   - Disable proxy" -ForegroundColor Gray
'''

    return Response(
        content=script,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="zetit-fna-proxy-setup.ps1"'
        }
    )
