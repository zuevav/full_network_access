from fastapi import APIRouter
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, CurrentClient
from app.models import Client
from app.schemas.portal import PortalProfileInfoResponse, VpnInfo, ProxyInfo
from app.services.profile_generator import ProfileGenerator
from app.api.system import get_configured_domain, get_configured_ports


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

    # Get configured settings - use domain for both VPN and Proxy
    domain = get_configured_domain()
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
            host=domain,
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
        pac_url=pac_url,
        access_token=client.access_token
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
    db: DBSession,
    mode: str = "ondemand"  # ondemand, always, full
):
    """Download iOS .mobileconfig with different VPN modes."""
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

    content = profile_generator.generate_ios_mobileconfig(client, mode=mode)

    mode_suffix = f"-{mode}" if mode != "ondemand" else ""
    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}{mode_suffix}.mobileconfig"'
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


@router.get("/proxy-setup")
async def download_proxy_setup_script(
    client: CurrentClient,
    db: DBSession
):
    """Download Windows proxy setup PowerShell script."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.proxy_account))
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    if client.proxy_account is None:
        return Response(content="Proxy not configured", status_code=400)

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
            "Content-Disposition": f'attachment; filename="zetit-fna-proxy-setup.ps1"'
        }
    )
