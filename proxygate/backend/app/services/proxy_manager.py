import subprocess
import signal
from typing import List
from dataclasses import dataclass, field

from app.config import settings


@dataclass
class ProxyClient:
    username: str
    password: str
    domains: List[str]
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
        """
        config = f'''daemon
# ProxyGate 3proxy configuration
# Auto-generated - DO NOT EDIT MANUALLY

nserver 1.1.1.1
nserver 8.8.8.8
nscache 65536
timeouts 10 10 60 180 180 1800 15 60

maxconn 500
stacksize 65536

log /var/log/3proxy/3proxy.log D
logformat "L%d-%m-%Y %H:%M:%S %U %C:%c %R:%r %O %I %T"
rotate 30

auth iponly strong
users ${self.PASSWD_PATH}

# === Per-client ACL ===
'''

        for client in clients:
            if client.is_active:
                # IP-based allow rules (no auth required)
                for ip in client.allowed_ips:
                    config += f'''
# IP whitelist for {client.username}
allow * {ip} * * *
'''

                # Domain-based allow rules (auth required)
                if client.domains:
                    domains_str = ",".join(client.domains)
                    config += f'''
# {client.username}
allow {client.username} * {domains_str} * *
'''

        config += f'''
# === Deny all other ===
deny *

# === Proxy servers ===
proxy -p{settings.proxy_http_port} -a -n
socks -p{settings.proxy_socks_port} -a -n
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
        """Full cycle: generate config + restart."""
        self.write_config(clients)
        return self.restart()


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
                domains=[d.domain for d in client.domains if d.is_active],
                is_active=True,
                allowed_ips=allowed_ips,
            ))

    ProxyManager().apply_changes(proxy_clients)
