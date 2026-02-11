#!/usr/bin/env python3
"""
Cron tasks for ProxyGate.

Usage:
  python scripts/cron_tasks.py check_payments
  python scripts/cron_tasks.py resolve_domains
  python scripts/cron_tasks.py collect_traffic_stats
  python scripts/cron_tasks.py backup

Recommended crontab:
  */15 * * * * /opt/proxygate/venv/bin/python /opt/proxygate/backend/scripts/cron_tasks.py check_payments
  */30 * * * * /opt/proxygate/venv/bin/python /opt/proxygate/backend/scripts/cron_tasks.py resolve_domains
  */5 * * * * /opt/proxygate/venv/bin/python /opt/proxygate/backend/scripts/cron_tasks.py collect_traffic_stats
  0 3 * * * /opt/proxygate/venv/bin/python /opt/proxygate/backend/scripts/cron_tasks.py backup
"""

import asyncio
import sys
import os
import shutil
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def check_payments():
    """Check payment status and deactivate expired clients."""
    from app.database import async_session_maker
    from app.services.payment_checker import PaymentChecker

    print(f"[{datetime.now()}] Checking payments...")

    checker = PaymentChecker()
    async with async_session_maker() as db:
        result = await checker.check_all(db)

    print(f"Checked: {result['checked']} clients")
    print(f"Deactivated: {result['deactivated']}")
    print(f"Warned: {result['warned']}")


async def resolve_domains():
    """Update domain -> IP mappings for all clients."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    import json

    from app.database import async_session_maker
    from app.models import Client
    from app.services.domain_resolver import DomainResolver

    print(f"[{datetime.now()}] Resolving domains...")

    resolver = DomainResolver()
    updated = 0

    async with async_session_maker() as db:
        result = await db.execute(
            select(Client)
            .options(
                selectinload(Client.vpn_config),
                selectinload(Client.domains)
            )
            .where(Client.is_active == True)
        )
        clients = result.scalars().all()

        for client in clients:
            if not client.vpn_config or not client.domains:
                continue

            # Resolve all active domains
            active_domains = [d.domain for d in client.domains if d.is_active]
            routes = resolver.resolve_domains(active_domains)

            # Update cached routes
            client.vpn_config.resolved_routes = json.dumps(routes)
            client.vpn_config.last_resolved = datetime.utcnow()
            updated += 1

        await db.commit()

    print(f"Updated routes for {updated} clients")


async def collect_traffic_stats():
    """Collect WireGuard peer traffic statistics and update DB."""
    from sqlalchemy import select
    from app.database import async_session_maker
    from app.models import WireguardConfig
    from app.services.wireguard_manager import WireGuardManager

    print(f"[{datetime.now()}] Collecting WireGuard traffic stats...")

    wg_manager = WireGuardManager()

    if not wg_manager.is_running():
        print("WireGuard is not running, skipping")
        return

    stats = wg_manager.get_peer_stats()
    if not stats:
        print("No peer stats available")
        return

    updated = 0
    async with async_session_maker() as db:
        result = await db.execute(
            select(WireguardConfig).where(WireguardConfig.is_active == True)
        )
        configs = result.scalars().all()

        for config in configs:
            peer_stat = stats.get(config.public_key)
            if peer_stat:
                config.traffic_up = peer_stat["tx"]
                config.traffic_down = peer_stat["rx"]
                if peer_stat["last_handshake"]:
                    config.last_handshake = datetime.utcfromtimestamp(peer_stat["last_handshake"])
                updated += 1

        await db.commit()

    print(f"Updated traffic stats for {updated}/{len(stats)} peers")


def backup():
    """Backup database file."""
    from app.config import settings

    print(f"[{datetime.now()}] Creating backup...")

    # Extract database path from URL
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    if db_path.startswith("./"):
        db_path = db_path[2:]

    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return

    # Create backup directory
    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    # Create backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"proxygate_{timestamp}.db")

    shutil.copy2(db_path, backup_path)
    print(f"Backup created: {backup_path}")

    # Clean old backups (keep last 30)
    backups = sorted([
        os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
        if f.endswith(".db")
    ])
    while len(backups) > 30:
        os.remove(backups.pop(0))
        print(f"Removed old backup")


def _add_iptables_block(ip: str):
    """Add iptables DROP rules for an IP on proxy ports (idempotent)."""
    import subprocess
    for port in ("3128", "1080"):
        # Check if rule already exists
        check = subprocess.run(
            ["iptables", "-C", "INPUT", "-s", ip, "-p", "tcp", "--dport", port, "-j", "DROP"],
            capture_output=True
        )
        if check.returncode != 0:
            subprocess.run(
                ["iptables", "-I", "INPUT", "-s", ip, "-p", "tcp", "--dport", port, "-j", "DROP"],
                capture_output=True
            )
            print(f"  iptables: blocked {ip}:{port}")


async def monitor_proxy_auth():
    """Parse 3proxy logs for failed auth attempts and record in security DB."""
    import re
    from pathlib import Path
    from app.database import async_session_maker
    from app.services.security_service import SecurityService

    LOG_DIR = Path("/var/log/3proxy")
    STATE_FILE = LOG_DIR / ".monitor_state"

    # Find today's log file
    today = datetime.now().strftime("%Y.%m.%d")
    log_file = LOG_DIR / f"3proxy.log.{today}"

    if not log_file.exists():
        print(f"[{datetime.now()}] No log file: {log_file}")
        return

    # Read last processed position
    last_pos = 0
    last_file = ""
    if STATE_FILE.exists():
        try:
            data = STATE_FILE.read_text().strip()
            parts = data.rsplit(":", 1)
            if len(parts) == 2:
                last_file = parts[0]
                last_pos = int(parts[1])
        except (ValueError, IOError):
            pass

    # Reset position if log file changed (new day)
    if last_file != str(log_file):
        last_pos = 0

    # Read new entries
    with open(log_file) as f:
        f.seek(last_pos)
        new_lines = f.readlines()
        new_pos = f.tell()

    if not new_lines:
        return

    # Parse failed attempts: entries with 0.0.0.0:0 as destination
    # Log format: date time username client_ip:port dest_ip:port bytes_out bytes_in request
    # Failed: 0.0.0.0:0 and 0 0
    failed_pattern = re.compile(
        r'\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2} (\S+) (\d+\.\d+\.\d+\.\d+):\d+ 0\.0\.0\.0:0 0 0 (.+)'
    )

    # Skip local/private IPs
    SKIP_IPS = {'127.0.0.1', '0.0.0.0', '::1'}

    def _is_private(ip):
        parts = ip.split('.')
        if len(parts) != 4:
            return True
        first, second = int(parts[0]), int(parts[1])
        return first == 10 or (first == 172 and 16 <= second <= 31) or (first == 192 and second == 168)

    # Aggregate by IP
    failed_by_ip = {}
    for line in new_lines:
        line = line.strip()
        if not line or "Accepting connections" in line or "Exiting thread" in line:
            continue
        m = failed_pattern.match(line)
        if m:
            username, client_ip, request = m.groups()
            if client_ip in SKIP_IPS or _is_private(client_ip):
                continue
            if username == '-':
                username = None
            if client_ip not in failed_by_ip:
                failed_by_ip[client_ip] = []
            failed_by_ip[client_ip].append({
                'username': username,
                'request': request,
            })

    if not failed_by_ip:
        # Save position even if no failed attempts
        STATE_FILE.write_text(f"{log_file}:{new_pos}")
        return

    total_attempts = sum(len(v) for v in failed_by_ip.values())
    print(f"[{datetime.now()}] Found {total_attempts} failed proxy auth attempts from {len(failed_by_ip)} IPs")

    async with async_session_maker() as db:
        svc = SecurityService(db)
        for ip, attempts in failed_by_ip.items():
            # Record up to 10 individual attempts per IP (avoid flooding DB)
            for attempt in attempts[:10]:
                blocked = await svc.record_failed_attempt(
                    ip_address=ip,
                    username=attempt['username'],
                    endpoint="3proxy",
                    user_agent=attempt['request'][:255] if attempt['request'] else None
                )
                if blocked:
                    print(f"  Blocked IP: {ip} ({blocked.reason})")
                    # Add iptables rule (only once per IP)
                    _add_iptables_block(ip)
                    break  # Stop recording more attempts for this IP

            if len(attempts) > 10:
                print(f"  IP {ip}: {len(attempts)} attempts (recorded first 10)")

    # Save position
    STATE_FILE.write_text(f"{log_file}:{new_pos}")
    print(f"Proxy auth monitoring complete")


def main():
    if len(sys.argv) < 2:
        print("Usage: python cron_tasks.py <task>")
        print("Tasks: check_payments, resolve_domains, collect_traffic_stats, backup, monitor_proxy_auth")
        sys.exit(1)

    task = sys.argv[1]

    if task == "check_payments":
        asyncio.run(check_payments())
    elif task == "resolve_domains":
        asyncio.run(resolve_domains())
    elif task == "collect_traffic_stats":
        asyncio.run(collect_traffic_stats())
    elif task == "monitor_proxy_auth":
        asyncio.run(monitor_proxy_auth())
    elif task == "backup":
        backup()
    else:
        print(f"Unknown task: {task}")
        sys.exit(1)


if __name__ == "__main__":
    main()
