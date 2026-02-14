import subprocess
import signal
import logging
from typing import List
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProxyDomain:
    domain: str
    include_subdomains: bool = True


@dataclass
class ProxyClient:
    username: str
    password: str
    domains: List[ProxyDomain]
    is_active: bool
    allowed_ips: List[str] = field(default_factory=list)


class ProxyManager:
    """
    Manages 3proxy configuration and service.

    Config: /etc/3proxy/3proxy.cfg
    Passwd: /etc/3proxy/passwd
    """

    CONFIG_PATH = "/etc/3proxy/3proxy.cfg"
    PASSWD_PATH = "/etc/3proxy/passwd"

    def generate_config(self, clients: List[ProxyClient]) -> str:
        """
        Generate full 3proxy configuration.

        Per-client ACL with domain whitelist and IP-based access.
        Connections from 127.0.0.1 (nginx TLS proxy) are allowed without auth —
        IP filtering is handled by iptables on nginx TLS ports.
        """
        config = f'''daemon
# ProxyGate 3proxy configuration
# Auto-generated - DO NOT EDIT MANUALLY

nserver 1.1.1.1
nserver 8.8.8.8
nscache 65536
timeouts 10 10 120 300 600 1800 5 60

maxconn 500
stacksize 262144

log /var/log/3proxy/3proxy.log D
logformat "L%d-%m-%Y %H:%M:%S %U %C:%c %R:%r %O %I %T"
rotate 30

auth iponly strong
users ${self.PASSWD_PATH}

# === Per-client ACL ===
'''

        # Collect all domains from all active clients for TLS proxy access
        all_domains_expanded = []
        for client in clients:
            if client.is_active and client.domains:
                for d in client.domains:
                    all_domains_expanded.append(d.domain)
                    if d.include_subdomains:
                        all_domains_expanded.append(f"*.{d.domain}")

        # Add server's own domain for PAC re-fetch through proxy
        try:
            from app.api.system import get_configured_domain
            server_domain = get_configured_domain()
            if server_domain and server_domain != "localhost":
                all_domains_expanded.append(server_domain)
                all_domains_expanded.append(f"*.{server_domain}")
        except Exception:
            pass

        # Deduplicate while preserving order
        seen = set()
        unique_domains = []
        for d in all_domains_expanded:
            if d not in seen:
                seen.add(d)
                unique_domains.append(d)

        # Allow TLS proxy connections (127.0.0.1) without auth
        # IP access control is enforced by iptables on nginx TLS ports (443/8080)
        if unique_domains:
            all_domains_str = ",".join(unique_domains)
            config += f'''
# TLS proxy passthrough — IP filtering done by iptables on ports 443/8080
allow * 127.0.0.1 {all_domains_str} * *
'''

        for client in clients:
            if client.is_active:
                # Build domain list for this client
                expanded = []
                if client.domains:
                    for d in client.domains:
                        expanded.append(d.domain)
                        if d.include_subdomains:
                            expanded.append(f"*.{d.domain}")
                domains_str = ",".join(expanded) if expanded else None

                # IP-based allow rules (no auth, restricted to client's domains)
                if domains_str and client.allowed_ips:
                    for ip in client.allowed_ips:
                        config += f'''
# IP whitelist for {client.username}
allow * {ip} {domains_str} * *
'''

                # Username-based allow rules (auth required)
                if domains_str:
                    config += f'''
# {client.username}
allow {client.username} * {domains_str} * *
'''

        config += f'''
# === Deny all other ===
deny *

# === Proxy servers ===
proxy -p3128 -a -n
socks -p1080 -a -n
'''
        return config

    def generate_passwd(self, clients: List[ProxyClient]) -> str:
        """
        Generate passwd file in 3proxy format.

        Format: username:CL:password
        CL = cleartext password
        """
        lines = []
        for client in clients:
            if client.is_active:
                lines.append(f"{client.username}:CL:{client.password}")
        return "\n".join(lines) + "\n"

    def write_config(self, clients: List[ProxyClient]) -> None:
        """Write configuration files."""
        # Write main config
        config = self.generate_config(clients)
        with open(self.CONFIG_PATH, 'w') as f:
            f.write(config)

        # Write passwd file
        passwd = self.generate_passwd(clients)
        with open(self.PASSWD_PATH, 'w') as f:
            f.write(passwd)

    def reload(self) -> bool:
        """
        Reload 3proxy configuration.

        Uses: kill -HUP $(pidof 3proxy)
        """
        try:
            result = subprocess.run(
                ["pidof", "3proxy"],
                capture_output=True,
                text=True,
                check=True
            )
            pid = int(result.stdout.strip().split()[0])

            import os
            os.kill(pid, signal.SIGHUP)
            return True

        except subprocess.CalledProcessError:
            print("3proxy not running")
            return False
        except (ValueError, IndexError, ProcessLookupError) as e:
            print(f"Failed to reload 3proxy: {e}")
            return False

    def restart(self) -> bool:
        """Restart 3proxy service."""
        try:
            subprocess.run(
                ["systemctl", "restart", "3proxy"],
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to restart 3proxy: {e}")
            return False
        except FileNotFoundError:
            return False

    def apply_changes(self, clients: List[ProxyClient]) -> bool:
        """Full cycle: generate config + restart + update iptables."""
        self.write_config(clients)
        result = self.restart()
        # Sync iptables PROXYGATE chain with all whitelisted IPs
        all_ips = set()
        for client in clients:
            if client.is_active:
                all_ips.update(client.allowed_ips)
        self.sync_iptables_whitelist(all_ips)
        return result

    @staticmethod
    def sync_iptables_whitelist(allowed_ips: set) -> None:
        """
        Sync PROXYGATE iptables chain with whitelisted IPs.

        Only whitelisted IPs can reach nginx TLS proxy ports (443/2053/8080).
        This replaces password auth — 3proxy allows 127.0.0.1 without auth.
        """
        chain = "PROXYGATE"
        try:
            # Ensure chain exists
            subprocess.run(
                ["iptables", "-N", chain],
                capture_output=True
            )
            # Flush existing rules
            subprocess.run(
                ["iptables", "-F", chain],
                capture_output=True, check=True
            )
            # Always allow localhost and server's own IP
            subprocess.run(
                ["iptables", "-A", chain, "-s", "127.0.0.1", "-j", "ACCEPT"],
                capture_output=True, check=True
            )
            # Get server IP
            try:
                from app.api.system import get_configured_server_ip
                server_ip = get_configured_server_ip()
                if server_ip and server_ip != "127.0.0.1":
                    subprocess.run(
                        ["iptables", "-A", chain, "-s", server_ip, "-j", "ACCEPT"],
                        capture_output=True, check=True
                    )
            except Exception:
                pass
            # Add whitelisted IPs
            for ip in sorted(allowed_ips):
                ip = ip.strip()
                if ip and ip != "127.0.0.1":
                    subprocess.run(
                        ["iptables", "-A", chain, "-s", ip, "-j", "ACCEPT"],
                        capture_output=True, check=True
                    )
            # Drop all other
            subprocess.run(
                ["iptables", "-A", chain, "-j", "DROP"],
                capture_output=True, check=True
            )
            # Ensure chain is referenced from INPUT for proxy ports
            for port in ["443", "2053", "8080", "3128", "1080"]:
                # Check if rule already exists
                check = subprocess.run(
                    ["iptables", "-C", "INPUT", "-p", "tcp", "--dport", port, "-j", chain],
                    capture_output=True
                )
                if check.returncode != 0:
                    subprocess.run(
                        ["iptables", "-I", "INPUT", "1", "-p", "tcp", "--dport", port, "-j", chain],
                        capture_output=True, check=True
                    )
            # Save iptables for persistence
            subprocess.run(
                "iptables-save > /etc/iptables.rules",
                shell=True, capture_output=True
            )
            logger.info(f"PROXYGATE iptables synced: {len(allowed_ips)} IPs")
        except Exception as e:
            logger.error(f"Failed to sync iptables: {e}")


async def rebuild_proxy_config(db):
    """Load all active clients with proxy accounts and rebuild 3proxy config."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models import Client

    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.proxy_account),
            selectinload(Client.domains),
        )
        .where(Client.is_active == True)
    )
    clients = result.scalars().all()

    proxy_clients = []
    for client in clients:
        if client.proxy_account and client.proxy_account.is_active:
            allowed_ips = []
            if client.proxy_account.allowed_ips:
                allowed_ips = [
                    ip.strip()
                    for ip in client.proxy_account.allowed_ips.split(",")
                    if ip.strip()
                ]
            proxy_clients.append(ProxyClient(
                username=client.proxy_account.username,
                password=client.proxy_account.password_plain,
                domains=[
                    ProxyDomain(domain=d.domain, include_subdomains=d.include_subdomains)
                    for d in client.domains if d.is_active
                ],
                is_active=True,
                allowed_ips=allowed_ips,
            ))

    ProxyManager().apply_changes(proxy_clients)
