import subprocess
import os
import ipaddress
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class WgClient:
    public_key: str
    preshared_key: Optional[str]
    assigned_ip: str
    is_active: bool


@dataclass
class WgServerSettings:
    private_key: str
    public_key: str
    interface: str
    listen_port: int
    server_ip: str
    subnet: str
    dns: str
    mtu: int
    wstunnel_enabled: bool
    wstunnel_port: int
    wstunnel_path: str


class WireGuardManager:
    """
    Manages WireGuard VPN server.

    WireGuard is a modern, fast VPN protocol with native support on iOS, Android, Windows, Mac, and Linux.
    """

    WG_DIR = "/etc/wireguard"
    WG_CONF = "/etc/wireguard/wg0.conf"
    WSTUNNEL_SERVICE = "/etc/systemd/system/wstunnel.service"

    @staticmethod
    def generate_keypair() -> Tuple[str, str]:
        """
        Generate a WireGuard key pair.

        Returns: (private_key, public_key)
        """
        try:
            # Generate private key
            private_result = subprocess.run(
                ["wg", "genkey"],
                capture_output=True,
                text=True,
                check=True
            )
            private_key = private_result.stdout.strip()

            # Derive public key
            public_result = subprocess.run(
                ["wg", "pubkey"],
                input=private_key,
                capture_output=True,
                text=True,
                check=True
            )
            public_key = public_result.stdout.strip()

            return private_key, public_key
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None, None

    @staticmethod
    def generate_preshared_key() -> Optional[str]:
        """Generate a preshared key for additional security."""
        try:
            result = subprocess.run(
                ["wg", "genpsk"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def is_installed(self) -> bool:
        """Check if WireGuard is installed."""
        try:
            result = subprocess.run(
                ["which", "wg"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def is_running(self) -> bool:
        """Check if WireGuard interface is up."""
        try:
            result = subprocess.run(
                ["wg", "show", "wg0"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_server_ip(self) -> Optional[str]:
        """Get the server's external IP address."""
        try:
            import urllib.request
            with urllib.request.urlopen('https://api.ipify.org', timeout=5) as response:
                return response.read().decode('utf-8').strip()
        except Exception:
            try:
                with urllib.request.urlopen('https://ifconfig.me', timeout=5) as response:
                    return response.read().decode('utf-8').strip()
            except Exception:
                return None

    def get_next_available_ip(self, subnet: str, used_ips: List[str]) -> Optional[str]:
        """
        Get the next available IP in the subnet.

        Skips .0 (network) and .1 (server) addresses.
        """
        network = ipaddress.ip_network(subnet, strict=False)
        used_set = set(used_ips)

        for ip in network.hosts():
            ip_str = str(ip)
            # Skip .0 and .1 (server uses .1)
            if ip_str.endswith('.0') or ip_str.endswith('.1'):
                continue
            if ip_str not in used_set:
                return ip_str

        return None

    def generate_server_config(self, server_settings: WgServerSettings, clients: List[WgClient]) -> str:
        """
        Generate WireGuard server configuration.
        """
        config = f"""# ProxyGate WireGuard Server Configuration
# Auto-generated - DO NOT EDIT MANUALLY

[Interface]
PrivateKey = {server_settings.private_key}
Address = {server_settings.server_ip}/24
ListenPort = {server_settings.listen_port}
MTU = {server_settings.mtu}

# Enable IP forwarding and NAT
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o $(ip route | grep default | awk '{{print $5}}') -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o $(ip route | grep default | awk '{{print $5}}') -j MASQUERADE
"""

        # Add peers (clients)
        for client in clients:
            if client.is_active:
                config += f"""
# Client
[Peer]
PublicKey = {client.public_key}
"""
                if client.preshared_key:
                    config += f"PresharedKey = {client.preshared_key}\n"
                config += f"AllowedIPs = {client.assigned_ip}/32\n"

        return config

    def generate_client_config(
            self,
            server_public_ip: str,
            server_settings: WgServerSettings,
            client_private_key: str,
            client_assigned_ip: str,
            client_preshared_key: Optional[str] = None
    ) -> str:
        """
        Generate WireGuard client configuration.
        """
        # Determine endpoint based on wstunnel
        if server_settings.wstunnel_enabled:
            # wstunnel endpoint - client connects via WebSocket
            endpoint = f"{server_public_ip}:{server_settings.wstunnel_port}"
        else:
            endpoint = f"{server_public_ip}:{server_settings.listen_port}"

        config = f"""[Interface]
PrivateKey = {client_private_key}
Address = {client_assigned_ip}/32
DNS = {server_settings.dns}
MTU = {server_settings.mtu}

[Peer]
PublicKey = {server_settings.public_key}
"""

        if client_preshared_key:
            config += f"PresharedKey = {client_preshared_key}\n"

        config += f"""AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {endpoint}
PersistentKeepalive = 25
"""

        return config

    def write_server_config(self, server_settings: WgServerSettings, clients: List[WgClient]) -> None:
        """Write WireGuard server configuration to file."""
        os.makedirs(self.WG_DIR, exist_ok=True)

        config = self.generate_server_config(server_settings, clients)

        with open(self.WG_CONF, 'w') as f:
            f.write(config)

        # Secure permissions
        os.chmod(self.WG_CONF, 0o600)

    def setup_wstunnel(self, port: int, wg_port: int, path: str) -> bool:
        """
        Setup wstunnel for WebSocket tunneling.

        This wraps WireGuard UDP traffic in WebSocket over HTTPS,
        making it look like normal web traffic.
        """
        # Create systemd service for wstunnel
        service = f"""[Unit]
Description=wstunnel - WebSocket Tunnel for WireGuard
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/wstunnel server --restrict-to 127.0.0.1:{wg_port} wss://0.0.0.0:{port}{path}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

        try:
            with open(self.WSTUNNEL_SERVICE, 'w') as f:
                f.write(service)

            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "enable", "wstunnel"], check=True)
            subprocess.run(["systemctl", "restart", "wstunnel"], check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, IOError):
            return False

    def install_wstunnel(self) -> bool:
        """Install wstunnel binary."""
        try:
            # Download latest wstunnel
            arch = subprocess.run(
                ["uname", "-m"],
                capture_output=True,
                text=True
            ).stdout.strip()

            if arch == "x86_64":
                arch_suffix = "x86_64-unknown-linux-musl"
            elif arch == "aarch64":
                arch_suffix = "aarch64-unknown-linux-musl"
            else:
                return False

            # Download from GitHub releases
            url = f"https://github.com/erebe/wstunnel/releases/latest/download/wstunnel_{arch_suffix}"

            subprocess.run(
                ["curl", "-L", "-o", "/usr/local/bin/wstunnel", url],
                check=True,
                timeout=120
            )
            subprocess.run(
                ["chmod", "+x", "/usr/local/bin/wstunnel"],
                check=True
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def start(self) -> bool:
        """Start WireGuard interface."""
        try:
            subprocess.run(
                ["wg-quick", "up", "wg0"],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError as e:
            # Already running is OK
            if "already exists" in str(e.stderr):
                return True
            print(f"Failed to start WireGuard: {e.stderr}")
            return False
        except FileNotFoundError:
            return False

    def stop(self) -> bool:
        """Stop WireGuard interface."""
        try:
            subprocess.run(
                ["wg-quick", "down", "wg0"],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError:
            return True  # Interface may not be up
        except FileNotFoundError:
            return False

    def reload(self) -> bool:
        """
        Reload WireGuard configuration.

        Uses wg syncconf for minimal disruption.
        """
        try:
            # First try to sync config without restarting
            subprocess.run(
                ["wg", "syncconf", "wg0", self.WG_CONF],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError:
            # If syncconf fails, restart the interface
            self.stop()
            return self.start()
        except FileNotFoundError:
            return False

    def enable_on_boot(self) -> bool:
        """Enable WireGuard to start on boot."""
        try:
            subprocess.run(
                ["systemctl", "enable", "wg-quick@wg0"],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def install(self) -> bool:
        """Install WireGuard."""
        try:
            # Try apt (Debian/Ubuntu)
            result = subprocess.run(
                ["apt", "install", "-y", "wireguard", "wireguard-tools"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True

            # Try yum (CentOS/RHEL)
            result = subprocess.run(
                ["yum", "install", "-y", "wireguard-tools"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0

        except FileNotFoundError:
            return False

    def get_peer_stats(self) -> Dict[str, Dict]:
        """
        Get statistics for all peers.

        Returns: {public_key: {"rx": bytes, "tx": bytes, "last_handshake": timestamp}}
        """
        try:
            result = subprocess.run(
                ["wg", "show", "wg0", "dump"],
                capture_output=True,
                text=True,
                check=True
            )

            stats = {}
            lines = result.stdout.strip().split('\n')

            # Skip first line (interface info)
            for line in lines[1:]:
                parts = line.split('\t')
                if len(parts) >= 6:
                    public_key = parts[0]
                    last_handshake = int(parts[4]) if parts[4] != '0' else None
                    rx_bytes = int(parts[5])
                    tx_bytes = int(parts[6]) if len(parts) > 6 else 0

                    stats[public_key] = {
                        "rx": rx_bytes,
                        "tx": tx_bytes,
                        "last_handshake": last_handshake
                    }

            return stats
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {}

    def add_peer(
            self,
            public_key: str,
            assigned_ip: str,
            preshared_key: Optional[str] = None
    ) -> bool:
        """Add a peer dynamically without restarting."""
        try:
            cmd = ["wg", "set", "wg0", "peer", public_key, "allowed-ips", f"{assigned_ip}/32"]
            if preshared_key:
                cmd.extend(["preshared-key", "/dev/stdin"])
                subprocess.run(cmd, input=preshared_key, capture_output=True, text=True, check=True)
            else:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def remove_peer(self, public_key: str) -> bool:
        """Remove a peer dynamically."""
        try:
            subprocess.run(
                ["wg", "set", "wg0", "peer", public_key, "remove"],
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_connection_info(
            self,
            server_settings: WgServerSettings,
            client_private_key: str,
            client_assigned_ip: str,
            client_preshared_key: Optional[str] = None
    ) -> Dict:
        """
        Get all connection information for a client.
        """
        server_ip = self.get_server_ip()

        config = self.generate_client_config(
            server_ip,
            server_settings,
            client_private_key,
            client_assigned_ip,
            client_preshared_key
        )

        return {
            "server_ip": server_ip,
            "server_port": server_settings.wstunnel_port if server_settings.wstunnel_enabled else server_settings.listen_port,
            "server_public_key": server_settings.public_key,
            "client_ip": client_assigned_ip,
            "dns": server_settings.dns,
            "wstunnel_enabled": server_settings.wstunnel_enabled,
            "config": config,
            "apps": {
                "ios": "WireGuard (App Store - бесплатно)",
                "android": "WireGuard (Google Play - бесплатно)",
                "windows": "WireGuard (wireguard.com - бесплатно)",
                "mac": "WireGuard (App Store - бесплатно)",
                "linux": "wireguard-tools (apt/yum)"
            }
        }
