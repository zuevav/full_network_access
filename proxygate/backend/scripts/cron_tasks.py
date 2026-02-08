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


def main():
    if len(sys.argv) < 2:
        print("Usage: python cron_tasks.py <task>")
        print("Tasks: check_payments, resolve_domains, collect_traffic_stats, backup")
        sys.exit(1)

    task = sys.argv[1]

    if task == "check_payments":
        asyncio.run(check_payments())
    elif task == "resolve_domains":
        asyncio.run(resolve_domains())
    elif task == "collect_traffic_stats":
        asyncio.run(collect_traffic_stats())
    elif task == "backup":
        backup()
    else:
        print(f"Unknown task: {task}")
        sys.exit(1)


if __name__ == "__main__":
    main()
