"""
SSL/Let's Encrypt API - Admin only
Handles SSL certificate management with Let's Encrypt
"""

import os
import json
import subprocess
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field, EmailStr

from app.api.deps import CurrentAdmin


router = APIRouter()

# Path to store SSL settings
SSL_SETTINGS_FILE = Path("/opt/proxygate/.ssl_settings.json")
SSL_LOG_FILE = Path("/opt/proxygate/.ssl_log.json")
NGINX_CONFIG_PATH = Path("/etc/nginx/sites-available/proxygate")
NGINX_CONFIG_ENABLED = Path("/etc/nginx/sites-enabled/proxygate")


class SSLSettings(BaseModel):
    domain: str = Field(..., description="Domain for SSL certificate")
    email: str = Field(..., description="Email for Let's Encrypt notifications")


class SSLStatus(BaseModel):
    configured: bool = False
    domain: Optional[str] = None
    email: Optional[str] = None
    certificate_exists: bool = False
    certificate_expiry: Optional[str] = None
    is_processing: bool = False
    log: List[str] = []


def load_ssl_settings() -> Optional[dict]:
    """Load saved SSL settings."""
    if SSL_SETTINGS_FILE.exists():
        try:
            with open(SSL_SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return None


def save_ssl_settings(data: dict):
    """Save SSL settings."""
    SSL_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SSL_SETTINGS_FILE, 'w') as f:
        json.dump(data, f)
    os.chmod(SSL_SETTINGS_FILE, 0o600)


def load_ssl_status() -> dict:
    """Load SSL status."""
    if SSL_LOG_FILE.exists():
        try:
            with open(SSL_LOG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        "is_processing": False,
        "log": []
    }


def save_ssl_status(data: dict):
    """Save SSL status."""
    SSL_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SSL_LOG_FILE, 'w') as f:
        json.dump(data, f)


def check_certificate_exists(domain: str) -> tuple[bool, Optional[str]]:
    """Check if certificate exists and get expiry date."""
    cert_path = Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem")
    if not cert_path.exists():
        return False, None

    try:
        result = subprocess.run(
            ["openssl", "x509", "-enddate", "-noout", "-in", str(cert_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # Parse output like "notAfter=Mar 15 12:00:00 2024 GMT"
            expiry = result.stdout.strip().replace("notAfter=", "")
            return True, expiry
    except:
        pass

    return cert_path.exists(), None


@router.get("/settings")
async def get_ssl_settings(admin: CurrentAdmin):
    """Get current SSL settings and status."""
    settings = load_ssl_settings()
    ssl_status = load_ssl_status()

    if settings:
        domain = settings.get("domain", "")
        cert_exists, cert_expiry = check_certificate_exists(domain)

        return SSLStatus(
            configured=True,
            domain=domain,
            email=settings.get("email", ""),
            certificate_exists=cert_exists,
            certificate_expiry=cert_expiry,
            is_processing=ssl_status.get("is_processing", False),
            log=ssl_status.get("log", [])
        )

    return SSLStatus(
        configured=False,
        is_processing=ssl_status.get("is_processing", False),
        log=ssl_status.get("log", [])
    )


@router.post("/settings")
async def save_ssl_settings_endpoint(settings: SSLSettings, admin: CurrentAdmin):
    """Save SSL settings (domain and email)."""
    save_ssl_settings({
        "domain": settings.domain,
        "email": settings.email
    })
    return {"success": True, "message": "Settings saved"}


async def run_certbot_process(domain: str, email: str):
    """Background task to obtain SSL certificate."""
    status_data = load_ssl_status()
    status_data["is_processing"] = True
    status_data["log"] = []
    save_ssl_status(status_data)

    log = []

    def add_log(message: str):
        log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        status_data["log"] = log
        save_ssl_status(status_data)

    try:
        add_log(f"Starting SSL certificate request for {domain}...")

        # Step 1: Stop nginx temporarily for standalone mode
        add_log("Stopping nginx temporarily...")
        subprocess.run(["systemctl", "stop", "nginx"], capture_output=True, timeout=30)

        # Step 2: Run certbot
        add_log("Running certbot to obtain certificate...")
        result = subprocess.run(
            [
                "certbot", "certonly",
                "--standalone",
                "--non-interactive",
                "--agree-tos",
                "--email", email,
                "-d", domain,
                "--preferred-challenges", "http"
            ],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            add_log(f"Certbot error: {result.stderr}")
            # Try webroot method if standalone fails
            add_log("Trying webroot method...")
            subprocess.run(["systemctl", "start", "nginx"], capture_output=True, timeout=30)

            result = subprocess.run(
                [
                    "certbot", "certonly",
                    "--webroot",
                    "--non-interactive",
                    "--agree-tos",
                    "--email", email,
                    "-d", domain,
                    "-w", "/var/www/proxygate"
                ],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                add_log(f"ERROR: Failed to obtain certificate: {result.stderr}")
                return
        else:
            # Restart nginx after standalone
            subprocess.run(["systemctl", "start", "nginx"], capture_output=True, timeout=30)

        add_log("Certificate obtained successfully!")

        # Step 3: Update nginx configuration for SSL
        add_log("Updating nginx configuration for SSL...")

        nginx_ssl_config = f'''server {{
    listen 80;
    listen [::]:80;
    server_name {domain};

    location /.well-known/acme-challenge/ {{
        root /var/www/proxygate;
    }}

    location / {{
        return 301 https://$server_name$request_uri;
    }}
}}

server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {domain};

    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    add_header Strict-Transport-Security "max-age=63072000" always;

    root /var/www/proxygate;
    index index.html;

    # API proxy
    location /api {{
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }}

    # SPA routing
    location / {{
        try_files $uri $uri/ /index.html;
    }}
}}
'''

        # Backup existing config
        if NGINX_CONFIG_PATH.exists():
            backup_path = NGINX_CONFIG_PATH.with_suffix('.bak')
            subprocess.run(["cp", str(NGINX_CONFIG_PATH), str(backup_path)], capture_output=True)

        # Write new config
        with open(NGINX_CONFIG_PATH, 'w') as f:
            f.write(nginx_ssl_config)

        add_log("Nginx configuration updated")

        # Step 4: Test nginx configuration
        add_log("Testing nginx configuration...")
        result = subprocess.run(
            ["nginx", "-t"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            add_log(f"ERROR: Nginx config test failed: {result.stderr}")
            # Restore backup
            backup_path = NGINX_CONFIG_PATH.with_suffix('.bak')
            if backup_path.exists():
                subprocess.run(["cp", str(backup_path), str(NGINX_CONFIG_PATH)], capture_output=True)
            return

        add_log("Nginx configuration valid")

        # Step 5: Reload nginx
        add_log("Reloading nginx...")
        result = subprocess.run(
            ["systemctl", "reload", "nginx"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            add_log(f"WARNING: Nginx reload had issues: {result.stderr}")
        else:
            add_log("Nginx reloaded successfully")

        # Step 6: Setup auto-renewal cron
        add_log("Setting up auto-renewal...")
        cron_job = "0 12 * * * /usr/bin/certbot renew --quiet && systemctl reload nginx"
        result = subprocess.run(
            ["bash", "-c", f'(crontab -l 2>/dev/null | grep -v certbot; echo "{cron_job}") | crontab -'],
            capture_output=True,
            text=True,
            timeout=30
        )

        add_log("SSL SETUP COMPLETE!")
        add_log(f"Your site is now available at https://{domain}")

    except subprocess.TimeoutExpired:
        add_log("ERROR: Command timed out")
    except Exception as e:
        add_log(f"ERROR: {str(e)}")
    finally:
        # Make sure nginx is running
        subprocess.run(["systemctl", "start", "nginx"], capture_output=True, timeout=30)
        status_data["is_processing"] = False
        save_ssl_status(status_data)


@router.post("/obtain")
async def obtain_certificate(background_tasks: BackgroundTasks, admin: CurrentAdmin):
    """Obtain SSL certificate from Let's Encrypt (runs in background)."""
    settings = load_ssl_settings()

    if not settings or not settings.get("domain") or not settings.get("email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain and email must be configured first"
        )

    status_data = load_ssl_status()
    if status_data.get("is_processing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Certificate request already in progress"
        )

    background_tasks.add_task(
        run_certbot_process,
        settings["domain"],
        settings["email"]
    )

    return {"success": True, "message": "Certificate request started"}


@router.post("/renew")
async def renew_certificate(admin: CurrentAdmin):
    """Manually renew SSL certificate."""
    settings = load_ssl_settings()

    if not settings or not settings.get("domain"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSL not configured"
        )

    domain = settings["domain"]
    cert_exists, _ = check_certificate_exists(domain)

    if not cert_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No certificate to renew. Obtain certificate first."
        )

    try:
        result = subprocess.run(
            ["certbot", "renew", "--cert-name", domain, "--force-renewal"],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Renewal failed: {result.stderr}"
            )

        # Reload nginx
        subprocess.run(["systemctl", "reload", "nginx"], capture_output=True, timeout=30)

        return {"success": True, "message": "Certificate renewed successfully"}

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Renewal timed out"
        )


@router.get("/log")
async def get_ssl_log(admin: CurrentAdmin):
    """Get the current SSL operation log."""
    status_data = load_ssl_status()
    return {
        "is_processing": status_data.get("is_processing", False),
        "log": status_data.get("log", [])
    }
