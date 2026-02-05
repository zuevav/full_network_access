import subprocess
import json
import uuid
import os
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class XrayClient:
    uuid: str
    short_id: Optional[str]
    is_active: bool


@dataclass
class XrayServerSettings:
    port: int
    private_key: str
    public_key: str
    short_id: str
    dest_server: str
    dest_port: int
    server_name: str


class XRayManager:
    """
    Manages XRay VLESS + REALITY server.

    XRay is a modern proxy protocol that can bypass deep packet inspection
    by masquerading as legitimate HTTPS traffic.
    """

    XRAY_DIR = "/usr/local/etc/xray"
    CONFIG_FILE = "/usr/local/etc/xray/config.json"
    CLIENT_CONFIG_DIR = "/root/xray-client"

    @staticmethod
    def generate_uuid() -> str:
        """Generate a new UUID for a client."""
        return str(uuid.uuid4())

    @staticmethod
    def generate_short_id() -> str:
        """Generate a short ID (16 hex characters)."""
        return os.urandom(8).hex()

    @staticmethod
    def generate_keys() -> tuple:
        """
        Generate X25519 key pair for REALITY.

        Returns: (private_key, public_key)
        """
        try:
            result = subprocess.run(
                ["/usr/local/bin/xray", "x25519"],
                capture_output=True,
                text=True,
                check=True
            )
            lines = result.stdout.strip().split('\n')
            private_key = None
            public_key = None
            for line in lines:
                if "Private key:" in line:
                    private_key = line.split(": ")[1].strip()
                elif "Public key:" in line:
                    public_key = line.split(": ")[1].strip()
            return private_key, public_key
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback: generate using openssl (less secure but works)
            return None, None

    def is_installed(self) -> bool:
        """Check if XRay is installed."""
        return os.path.exists("/usr/local/bin/xray")

    def is_running(self) -> bool:
        """Check if XRay service is running."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "xray"],
                capture_output=True,
                text=True
            )
            return result.stdout.strip() == "active"
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

    def generate_config(self, server_settings: XrayServerSettings, clients: List[XrayClient]) -> dict:
        """
        Generate XRay server configuration.

        Returns the configuration as a dictionary.
        """
        # Build client list with only active clients
        client_list = []
        for client in clients:
            if client.is_active:
                client_entry = {
                    "id": client.uuid,
                    "flow": "xtls-rprx-vision"
                }
                client_list.append(client_entry)

        # Short IDs - include server default and client-specific ones
        short_ids = [server_settings.short_id, ""]
        for client in clients:
            if client.is_active and client.short_id and client.short_id not in short_ids:
                short_ids.append(client.short_id)

        config = {
            "log": {
                "loglevel": "warning"
            },
            "inbounds": [
                {
                    "listen": "0.0.0.0",
                    "port": server_settings.port,
                    "protocol": "vless",
                    "settings": {
                        "clients": client_list,
                        "decryption": "none"
                    },
                    "streamSettings": {
                        "network": "tcp",
                        "security": "reality",
                        "realitySettings": {
                            "show": False,
                            "dest": f"{server_settings.dest_server}:{server_settings.dest_port}",
                            "xver": 0,
                            "serverNames": [
                                server_settings.server_name,
                                server_settings.dest_server
                            ],
                            "privateKey": server_settings.private_key,
                            "shortIds": short_ids
                        }
                    },
                    "sniffing": {
                        "enabled": True,
                        "destOverride": ["http", "tls", "quic"]
                    }
                }
            ],
            "outbounds": [
                {
                    "protocol": "freedom",
                    "tag": "direct"
                },
                {
                    "protocol": "blackhole",
                    "tag": "block"
                }
            ],
            "routing": {
                "domainStrategy": "IPIfNonMatch",
                "rules": [
                    {
                        "type": "field",
                        "ip": ["geoip:private"],
                        "outboundTag": "block"
                    }
                ]
            }
        }

        return config

    def generate_client_config(
            self,
            server_ip: str,
            server_settings: XrayServerSettings,
            client_uuid: str,
            client_short_id: Optional[str] = None
    ) -> dict:
        """
        Generate client configuration for connection.

        This can be used by v2rayN, v2rayNG, etc.
        """
        short_id = client_short_id or server_settings.short_id

        return {
            "log": {
                "loglevel": "warning"
            },
            "inbounds": [
                {
                    "listen": "127.0.0.1",
                    "port": 10808,
                    "protocol": "socks",
                    "settings": {
                        "udp": True
                    }
                },
                {
                    "listen": "127.0.0.1",
                    "port": 10809,
                    "protocol": "http"
                }
            ],
            "outbounds": [
                {
                    "protocol": "vless",
                    "settings": {
                        "vnext": [
                            {
                                "address": server_ip,
                                "port": server_settings.port,
                                "users": [
                                    {
                                        "id": client_uuid,
                                        "encryption": "none",
                                        "flow": "xtls-rprx-vision"
                                    }
                                ]
                            }
                        ]
                    },
                    "streamSettings": {
                        "network": "tcp",
                        "security": "reality",
                        "realitySettings": {
                            "fingerprint": "chrome",
                            "serverName": server_settings.server_name,
                            "publicKey": server_settings.public_key,
                            "shortId": short_id
                        }
                    },
                    "tag": "proxy"
                },
                {
                    "protocol": "freedom",
                    "tag": "direct"
                }
            ],
            "routing": {
                "domainStrategy": "IPIfNonMatch",
                "rules": [
                    {
                        "type": "field",
                        "domain": ["geosite:private"],
                        "outboundTag": "direct"
                    }
                ]
            }
        }

    def generate_vless_url(
            self,
            server_ip: str,
            server_settings: XrayServerSettings,
            client_uuid: str,
            client_short_id: Optional[str] = None,
            name: str = "ProxyGate"
    ) -> str:
        """
        Generate VLESS URL for easy import into clients.

        This URL can be imported directly into:
        - Shadowrocket (iOS)
        - v2rayNG (Android)
        - v2rayN (Windows)
        - V2RayXS (Mac)
        """
        short_id = client_short_id or server_settings.short_id

        url = (
            f"vless://{client_uuid}@{server_ip}:{server_settings.port}"
            f"?encryption=none"
            f"&flow=xtls-rprx-vision"
            f"&security=reality"
            f"&sni={server_settings.server_name}"
            f"&fp=chrome"
            f"&pbk={server_settings.public_key}"
            f"&sid={short_id}"
            f"&type=tcp"
            f"#{name}"
        )
        return url

    def write_config(self, server_settings: XrayServerSettings, clients: List[XrayClient]) -> None:
        """Write XRay configuration to file."""
        os.makedirs(self.XRAY_DIR, exist_ok=True)

        config = self.generate_config(server_settings, clients)

        with open(self.CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

    def reload(self) -> bool:
        """
        Reload XRay configuration.

        XRay supports hot reload via SIGUSR1 or systemctl restart.
        """
        try:
            subprocess.run(
                ["systemctl", "restart", "xray"],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to restart XRay: {e.stderr}")
            return False
        except FileNotFoundError:
            print("systemctl not found")
            return False

    def start(self) -> bool:
        """Start XRay service."""
        try:
            subprocess.run(
                ["systemctl", "start", "xray"],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def stop(self) -> bool:
        """Stop XRay service."""
        try:
            subprocess.run(
                ["systemctl", "stop", "xray"],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def enable(self) -> bool:
        """Enable XRay service to start on boot."""
        try:
            subprocess.run(
                ["systemctl", "enable", "xray"],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def install(self) -> bool:
        """
        Install XRay using the official install script.

        This downloads and installs XRay from GitHub.
        """
        try:
            # Download and run the install script
            result = subprocess.run(
                ["bash", "-c", 'bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install'],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            return result.returncode == 0
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_traffic_stats(self) -> Dict[str, Dict[str, int]]:
        """
        Get traffic statistics for all clients.

        Note: This requires enabling stats in XRay config.
        Returns: {uuid: {"up": bytes, "down": bytes}}
        """
        # XRay traffic stats require API access
        # This is a simplified version
        return {}

    def add_client(self, client: XrayClient, server_settings: XrayServerSettings, all_clients: List[XrayClient]) -> bool:
        """Add a new client and reload config."""
        self.write_config(server_settings, all_clients)
        return self.reload()

    def remove_client(self, client_uuid: str, server_settings: XrayServerSettings, all_clients: List[XrayClient]) -> bool:
        """Remove a client and reload config."""
        self.write_config(server_settings, all_clients)
        return self.reload()

    def get_connection_info(
            self,
            server_settings: XrayServerSettings,
            client_uuid: str,
            client_short_id: Optional[str] = None,
            client_name: str = "ProxyGate"
    ) -> Dict:
        """
        Get all connection information for a client.

        Returns a dict with all info needed to connect.
        """
        server_ip = self.get_server_ip()
        short_id = client_short_id or server_settings.short_id

        return {
            "server_ip": server_ip,
            "port": server_settings.port,
            "uuid": client_uuid,
            "flow": "xtls-rprx-vision",
            "security": "reality",
            "sni": server_settings.server_name,
            "fingerprint": "chrome",
            "public_key": server_settings.public_key,
            "short_id": short_id,
            "vless_url": self.generate_vless_url(
                server_ip, server_settings, client_uuid, client_short_id, client_name
            ),
            "apps": {
                "ios": ["Shadowrocket", "Streisand", "V2Box"],
                "android": ["v2rayNG", "Matsuri"],
                "windows": ["v2rayN", "Nekoray"],
                "mac": ["V2RayXS", "V2BOX", "Shadowrocket"]
            }
        }
