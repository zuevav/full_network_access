import subprocess
import signal
from typing import List
from dataclasses import dataclass

from app.config import settings


@dataclass
class ProxyClient:
    username: str
    password: str
    domains: List[str]
    is_active: bool


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

        Per-client ACL with domain whitelist.
        """
        config = f'''# ProxyGate 3proxy configuration
# Auto-generated - DO NOT EDIT MANUALLY

nserver 1.1.1.1
nserver 8.8.8.8
nscache 65536
timeouts 1 5 30 60 180 1800 15 60

log /var/log/3proxy/3proxy.log D
logformat "L%d-%m-%Y %H:%M:%S %U %C:%c %R:%r %O %I %T"
rotate 30

auth strong
users ${self.PASSWD_PATH}

# === Per-client ACL ===
'''

        for client in clients:
            if client.is_active and client.domains:
                domains_str = ",".join(client.domains)
                config += f'''
# {client.username}
allow {client.username} * * {domains_str} *
'''

        config += f'''
# === Deny all other ===
deny *

# === Proxy servers ===
proxy -p{settings.proxy_http_port} -a
socks -p{settings.proxy_socks_port} -a
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
        """Full cycle: generate config + reload."""
        self.write_config(clients)
        return self.reload()
