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
    Manages XRay VLESS + WebSocket server (behind Cloudflare CDN).

    XRay listens locally on WS, nginx terminates TLS on port 443,
    Cloudflare CDN hides the server IP from ISP DPI.
    """

    XRAY_DIR = "/usr/local/etc/xray"
    CONFIG_FILE = "/usr/local/etc/xray/config.json"
    CLIENT_CONFIG_DIR = "/root/xray-client"
    WS_PATH = "/ray"
    WS_LOCAL_PORT = 10443

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
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip()
                if key in ("private key", "privatekey"):
                    private_key = value
                elif key in ("public key", "publickey", "password"):
                    public_key = value
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
        Generate XRay server configuration (VLESS + WebSocket).

        XRay listens locally, nginx handles TLS termination.
        """
        client_list = []
        for client in clients:
            if client.is_active:
                client_list.append({"id": client.uuid})

        config = {
            "log": {
                "loglevel": "warning"
            },
            "inbounds": [
                {
                    "listen": "127.0.0.1",
                    "port": self.WS_LOCAL_PORT,
                    "protocol": "vless",
                    "settings": {
                        "clients": client_list,
                        "decryption": "none"
                    },
                    "streamSettings": {
                        "network": "ws",
                        "wsSettings": {
                            "path": self.WS_PATH
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
            domain: str,
            server_settings: XrayServerSettings,
            client_uuid: str,
            client_short_id: Optional[str] = None
    ) -> dict:
        """Generate client configuration for VLESS+WS+TLS connection."""
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
                                "address": domain,
                                "port": server_settings.port,
                                "users": [
                                    {
                                        "id": client_uuid,
                                        "encryption": "none"
                                    }
                                ]
                            }
                        ]
                    },
                    "streamSettings": {
                        "network": "ws",
                        "security": "tls",
                        "tlsSettings": {
                            "serverName": domain
                        },
                        "wsSettings": {
                            "path": self.WS_PATH,
                            "headers": {
                                "Host": domain
                            }
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
            domain: str,
            server_settings: XrayServerSettings,
            client_uuid: str,
            client_short_id: Optional[str] = None,
            name: str = "ProxyGate"
    ) -> str:
        """
        Generate VLESS+WS+TLS URL for easy import into clients.

        Traffic: client → Cloudflare CDN (TLS) → nginx (TLS) → XRay (WS)
        """
        from urllib.parse import quote
        url = (
            f"vless://{client_uuid}@{domain}:{server_settings.port}"
            f"?encryption=none"
            f"&security=tls"
            f"&sni={domain}"
            f"&type=ws"
            f"&host={domain}"
            f"&path={quote(self.WS_PATH)}"
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
            domain: str,
            server_settings: XrayServerSettings,
            client_uuid: str,
            client_short_id: Optional[str] = None,
            client_name: str = "ProxyGate"
    ) -> Dict:
        """Get all connection information for a client (VLESS+WS+TLS via CDN)."""
        return {
            "domain": domain,
            "port": server_settings.port,
            "uuid": client_uuid,
            "transport": "ws",
            "security": "tls",
            "sni": domain,
            "ws_path": self.WS_PATH,
            "vless_url": self.generate_vless_url(
                domain, server_settings, client_uuid, client_short_id, client_name
            ),
            "apps": {
                "ios": ["Shadowrocket", "Streisand", "V2Box"],
                "android": ["v2rayNG", "Matsuri"],
                "windows": ["v2rayN", "Nekoray"],
                "mac": ["V2RayXS", "V2BOX", "Shadowrocket"]
            }
        }
