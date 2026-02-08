"""
System Settings and Status API - Admin only
Handles system configuration and service monitoring
"""

import os
import json
import socket
import subprocess
from typing import Optional, List, Dict
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.api.deps import CurrentAdmin, DBSession
from app.models import VpnConfig
from app.services.ikev2_manager import IKEv2Manager, VpnClient


router = APIRouter()

# Path to store system settings
SYSTEM_SETTINGS_FILE = Path("/opt/proxygate/.system_settings.json")

# Version file locations (check code directory first, then root)
VERSION_PATHS = [
    Path("/opt/proxygate/proxygate/VERSION"),  # Code directory (priority)
    Path("/opt/proxygate/VERSION"),             # Root directory (fallback)
]

def get_app_version() -> str:
    """Get application version from VERSION file (reads fresh each time)."""
    for path in VERSION_PATHS:
        if path.exists():
            try:
                return path.read_text().strip()
            except:
                pass
    return "unknown"


class SystemSettings(BaseModel):
    domain: str = Field(default="", description="Main domain for the system")
    server_ip: str = Field(default="", description="Server IP address")
    vpn_subnet: str = Field(default="10.10.10.0/24", description="VPN subnet")
    dns_servers: str = Field(default="8.8.8.8,8.8.4.4", description="DNS servers")
    http_proxy_port: int = Field(default=3128, description="HTTP proxy port")
    socks_proxy_port: int = Field(default=1080, description="SOCKS5 proxy port")


class ServiceStatus(BaseModel):
    name: str
    display_name: str
    status: str  # running, stopped, error
    port: Optional[int] = None
    port_open: Optional[bool] = None


class SystemStatusResponse(BaseModel):
    services: List[ServiceStatus]
    system_info: Dict


def load_system_settings() -> dict:
    """Load saved system settings."""
    defaults = {
        "domain": "",
        "server_ip": get_server_ip(),
        "vpn_subnet": "10.10.10.0/24",
        "dns_servers": "8.8.8.8,8.8.4.4",
        "http_proxy_port": 3128,
        "socks_proxy_port": 1080
    }

    if SYSTEM_SETTINGS_FILE.exists():
        try:
            with open(SYSTEM_SETTINGS_FILE, 'r') as f:
                saved = json.load(f)
                defaults.update(saved)
        except:
            pass

    return defaults


def get_configured_domain() -> str:
    """Get the configured domain from system settings."""
    settings = load_system_settings()
    return settings.get("domain", "") or "localhost"


def get_configured_server_ip() -> str:
    """Get the configured server IP from system settings."""
    settings = load_system_settings()
    return settings.get("server_ip", "") or get_server_ip() or "127.0.0.1"


def get_configured_ports() -> tuple:
    """Get HTTP and SOCKS proxy ports from system settings."""
    settings = load_system_settings()
    return (
        settings.get("http_proxy_port", 3128),
        settings.get("socks_proxy_port", 1080)
    )


def save_system_settings(data: dict):
    """Save system settings."""
    SYSTEM_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SYSTEM_SETTINGS_FILE, 'w') as f:
        json.dump(data, f)
    os.chmod(SYSTEM_SETTINGS_FILE, 0o600)


def get_server_ip() -> str:
    """Get server's public IP."""
    try:
        # Try to get public IP
        result = subprocess.run(
            ["curl", "-s", "ifconfig.me"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass

    # Fallback to local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return ""


def check_service_status(service_name: str, alternatives: list = None) -> str:
    """Check if a systemd service is running. Try alternatives if main name fails."""
    names_to_try = [service_name]
    if alternatives:
        names_to_try.extend(alternatives)

    for name in names_to_try:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", name],
                capture_output=True,
                text=True,
                timeout=5
            )
            status = result.stdout.strip()
            if status == "active":
                return "running"
            elif status == "inactive":
                return "stopped"
            # If found but not active/inactive, continue to next alternative
            elif status in ["failed", "activating", "deactivating"]:
                return "error"
        except:
            continue

    return "stopped"  # Service not found = stopped


def check_port_open(port: int, host: str = "127.0.0.1", udp: bool = False) -> bool:
    """Check if a port is open (TCP or UDP)."""
    try:
        if udp:
            # For UDP, we can't really check if it's open, so just return True
            # if we can bind to it (meaning it's in use)
            # Instead, check if process is listening on the port
            result = subprocess.run(
                ["ss", "-uln", f"sport = :{port}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return str(port) in result.stdout
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
    except:
        return False


def get_system_info() -> dict:
    """Get system information."""
    info = {
        "hostname": "",
        "uptime": "",
        "memory_usage": "",
        "disk_usage": ""
    }

    # Hostname
    try:
        result = subprocess.run(["hostname"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info["hostname"] = result.stdout.strip()
    except Exception:
        # Fallback: try reading /etc/hostname
        try:
            with open("/etc/hostname") as f:
                info["hostname"] = f.read().strip()
        except:
            pass

    # Uptime - try different approaches
    try:
        result = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            info["uptime"] = result.stdout.strip().replace("up ", "")
        else:
            # Fallback: parse regular uptime output
            result = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Parse "up X days, H:MM" format
                output = result.stdout.strip()
                if "up" in output:
                    up_part = output.split("up")[1].split(",")[0].strip()
                    info["uptime"] = up_part
    except Exception:
        # Fallback: read from /proc/uptime
        try:
            with open("/proc/uptime") as f:
                uptime_seconds = float(f.read().split()[0])
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                if days > 0:
                    info["uptime"] = f"{days}d {hours}h {minutes}m"
                else:
                    info["uptime"] = f"{hours}h {minutes}m"
        except:
            pass

    # Memory
    try:
        result = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 3:
                    info["memory_usage"] = f"{parts[2]} / {parts[1]}"
    except Exception:
        # Fallback: read from /proc/meminfo
        try:
            with open("/proc/meminfo") as f:
                meminfo = f.read()
                total = used = 0
                for line in meminfo.split('\n'):
                    if line.startswith("MemTotal:"):
                        total = int(line.split()[1]) // 1024  # MB
                    elif line.startswith("MemAvailable:"):
                        available = int(line.split()[1]) // 1024  # MB
                        used = total - available
                if total > 0:
                    info["memory_usage"] = f"{used}MB / {total}MB"
        except:
            pass

    # Disk
    try:
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 5:
                    info["disk_usage"] = f"{parts[2]} / {parts[1]} ({parts[4]})"
    except Exception:
        pass

    return info


@router.get("/version")
async def get_version():
    """Get application version (no auth required, reads fresh each time)."""
    return {"version": get_app_version()}


@router.get("/settings")
async def get_settings(admin: CurrentAdmin):
    """Get current system settings."""
    settings = load_system_settings()
    return settings


@router.post("/settings")
async def save_settings(settings: SystemSettings, admin: CurrentAdmin):
    """Save system settings."""
    save_system_settings({
        "domain": settings.domain,
        "server_ip": settings.server_ip,
        "vpn_subnet": settings.vpn_subnet,
        "dns_servers": settings.dns_servers,
        "http_proxy_port": settings.http_proxy_port,
        "socks_proxy_port": settings.socks_proxy_port
    })
    return {"success": True, "message": "Settings saved"}


@router.get("/status", response_model=SystemStatusResponse)
async def get_status(admin: CurrentAdmin):
    """Get system and service status."""
    settings = load_system_settings()

    # Define services to check with alternative names
    services = [
        {
            "name": "nginx",
            "display_name": "Nginx Web Server",
            "ports": [80, 443],
            "alternatives": [],
            "udp": False
        },
        {
            "name": "proxygate",
            "display_name": "ProxyGate Backend",
            "ports": [8000],
            "alternatives": ["proxygate.service"],
            "udp": False
        },
        {
            "name": "strongswan-starter",
            "display_name": "StrongSwan VPN",
            "ports": [500],
            "alternatives": ["strongswan", "ipsec", "charon"],
            "udp": True  # IKE uses UDP port 500
        },
        {
            "name": "3proxy",
            "display_name": "3proxy HTTP/SOCKS",
            "ports": [settings.get("http_proxy_port", 3128), settings.get("socks_proxy_port", 1080)],
            "alternatives": ["3proxy.service"],
            "udp": False
        },
        {
            "name": "postgresql",
            "display_name": "PostgreSQL Database",
            "ports": [5432],
            "alternatives": ["postgresql@14-main", "postgresql@15-main", "postgresql@16-main", "postgres"],
            "udp": False
        }
    ]

    service_statuses = []
    for svc in services:
        svc_status = check_service_status(svc["name"], svc.get("alternatives", []))

        # Check first port for status indicator
        port = svc["ports"][0] if svc["ports"] else None
        is_udp = svc.get("udp", False)
        port_open = check_port_open(port, udp=is_udp) if port else None

        # If systemctl says stopped but port is open, service is likely running
        if svc_status == "stopped" and port_open:
            svc_status = "running"

        service_statuses.append(ServiceStatus(
            name=svc["name"],
            display_name=svc["display_name"],
            status=svc_status,
            port=port,
            port_open=port_open
        ))

    return SystemStatusResponse(
        services=service_statuses,
        system_info=get_system_info()
    )


@router.post("/restart/{service_name}")
async def restart_service(service_name: str, admin: CurrentAdmin):
    """Restart a specific service."""
    allowed_services = {"nginx", "proxygate", "strongswan", "strongswan-starter", "3proxy", "postgresql", "wg-quick@wg0", "xray"}

    if service_name not in allowed_services:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Service {service_name} is not allowed to be restarted"
        )

    try:
        result = subprocess.run(
            ["systemctl", "restart", service_name],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to restart service: {result.stderr}"
            )

        return {"success": True, "message": f"Service {service_name} restarted"}

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Service restart timed out"
        )


class VpnSyncResponse(BaseModel):
    success: bool
    message: str
    clients_count: int
    details: List[str]


@router.post("/vpn/sync", response_model=VpnSyncResponse)
async def sync_vpn_config(
    db: DBSession,
    admin: CurrentAdmin
):
    """
    Synchronize VPN configuration.

    This endpoint:
    1. Creates swanctl directory structure if needed
    2. Links Let's Encrypt certificates
    3. Generates connections.conf and secrets.conf
    4. Reloads strongSwan
    """
    details = []

    # Get configured domain
    settings = load_system_settings()
    domain = settings.get("domain", "")

    if not domain or domain == "localhost":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain must be configured in system settings before syncing VPN"
        )

    # Paths
    swanctl_dir = Path("/etc/swanctl")
    conf_dir = swanctl_dir / "conf.d"
    x509_dir = swanctl_dir / "x509"
    private_dir = swanctl_dir / "private"
    letsencrypt_dir = Path(f"/etc/letsencrypt/live/{domain}")

    # Create directories if needed
    try:
        for d in [conf_dir, x509_dir, private_dir]:
            d.mkdir(parents=True, exist_ok=True)
            details.append(f"Created directory: {d}")
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Permission denied creating directories: {e}"
        )

    # Check and link Let's Encrypt certificates
    le_fullchain = letsencrypt_dir / "fullchain.pem"
    le_privkey = letsencrypt_dir / "privkey.pem"

    if not le_fullchain.exists() or not le_privkey.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Let's Encrypt certificates not found at {letsencrypt_dir}. "
                   "Please obtain SSL certificate first."
        )

    # Create symlinks
    try:
        cert_link = x509_dir / "fullchain.pem"
        key_link = private_dir / "privkey.pem"

        # Remove existing links/files
        if cert_link.exists() or cert_link.is_symlink():
            cert_link.unlink()
        if key_link.exists() or key_link.is_symlink():
            key_link.unlink()

        # Create new symlinks
        cert_link.symlink_to(le_fullchain)
        key_link.symlink_to(le_privkey)

        details.append(f"Linked certificate: {le_fullchain} -> {cert_link}")
        details.append(f"Linked private key: {le_privkey} -> {key_link}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link certificates: {e}"
        )

    # Get all VPN configs from database
    result = await db.execute(select(VpnConfig))
    vpn_configs = result.scalars().all()

    # Convert to VpnClient objects
    clients = [
        VpnClient(
            username=vc.username,
            password=vc.password,
            is_active=vc.is_active
        )
        for vc in vpn_configs
    ]

    active_count = len([c for c in clients if c.is_active])
    details.append(f"Found {len(clients)} VPN clients ({active_count} active)")

    # Generate and write configuration
    manager = IKEv2Manager()

    try:
        manager.write_config(clients)
        details.append(f"Wrote {manager.CONNECTIONS_FILE}")
        details.append(f"Wrote {manager.SECRETS_FILE}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write configuration: {e}"
        )

    # Reload strongSwan
    try:
        result = subprocess.run(
            ["swanctl", "--load-all"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            details.append(f"swanctl --load-all warning: {result.stderr}")
        else:
            details.append("Reloaded strongSwan configuration")

    except FileNotFoundError:
        details.append("WARNING: swanctl not found - strongSwan may need manual restart")
    except subprocess.TimeoutExpired:
        details.append("WARNING: swanctl reload timed out")
    except Exception as e:
        details.append(f"WARNING: Failed to reload strongSwan: {e}")

    return VpnSyncResponse(
        success=True,
        message=f"VPN configuration synced for {active_count} active clients",
        clients_count=active_count,
        details=details
    )
