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
from pydantic import BaseModel, Field

from app.api.deps import CurrentAdmin


router = APIRouter()

# Path to store system settings
SYSTEM_SETTINGS_FILE = Path("/opt/proxygate/.system_settings.json")


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


def check_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is open."""
    try:
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
            "alternatives": []
        },
        {
            "name": "proxygate",
            "display_name": "ProxyGate Backend",
            "ports": [8000],
            "alternatives": ["proxygate.service"]
        },
        {
            "name": "strongswan",
            "display_name": "StrongSwan VPN",
            "ports": [500],
            "alternatives": ["strongswan-starter", "ipsec", "charon"]
        },
        {
            "name": "3proxy",
            "display_name": "3proxy HTTP/SOCKS",
            "ports": [settings.get("http_proxy_port", 3128), settings.get("socks_proxy_port", 1080)],
            "alternatives": ["3proxy.service"]
        },
        {
            "name": "postgresql",
            "display_name": "PostgreSQL Database",
            "ports": [5432],
            "alternatives": ["postgresql@14-main", "postgresql@15-main", "postgresql@16-main", "postgres"]
        }
    ]

    service_statuses = []
    for svc in services:
        svc_status = check_service_status(svc["name"], svc.get("alternatives", []))

        # Check first port for status indicator
        port = svc["ports"][0] if svc["ports"] else None
        port_open = check_port_open(port) if port else None

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
    allowed_services = ["nginx", "proxygate", "strongswan", "3proxy", "postgresql"]

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
