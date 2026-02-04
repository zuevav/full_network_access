import subprocess
from typing import List, Dict, Optional
from dataclasses import dataclass

from app.config import settings
from app.api.system import get_configured_domain


@dataclass
class VpnClient:
    username: str
    password: str
    is_active: bool


class IKEv2Manager:
    """
    Manages strongSwan IKEv2/IPsec VPN server.

    Uses swanctl (new interface) instead of deprecated ipsec.
    Configuration: /etc/swanctl/conf.d/
    Secrets (EAP): /etc/swanctl/conf.d/secrets.conf
    """

    SWANCTL_DIR = "/etc/swanctl"
    CONF_DIR = "/etc/swanctl/conf.d"
    CONNECTIONS_FILE = f"{CONF_DIR}/connections.conf"
    SECRETS_FILE = f"{CONF_DIR}/secrets.conf"

    def generate_connections_conf(self) -> str:
        """
        Generate /etc/swanctl/conf.d/connections.conf

        One shared connection for all clients.
        """
        # Use configured domain for server identity (must match client profiles)
        server_id = get_configured_domain()

        return f'''# ProxyGate strongSwan configuration
# Auto-generated - DO NOT EDIT MANUALLY

connections {{
    proxygate {{
        version = 2
        proposals = aes256-sha256-modp2048,aes128-sha256-modp2048
        rekey_time = 0s
        unique = replace
        pools = client_pool
        fragmentation = yes
        dpd_delay = 30s
        send_certreq = no

        local {{
            auth = pubkey
            certs = fullchain.pem
            id = {server_id}
        }}

        remote {{
            auth = eap-mschapv2
            eap_id = %any
        }}

        children {{
            proxygate-net {{
                local_ts = 0.0.0.0/0
                esp_proposals = aes256-sha256,aes128-sha256
                dpd_action = clear
                rekey_time = 0s
            }}
        }}
    }}
}}

pools {{
    client_pool {{
        addrs = {settings.ikev2_pool_subnet}
        dns = {settings.ikev2_dns}
    }}
}}
'''

    def generate_secrets_conf(self, clients: List[VpnClient]) -> str:
        """
        Generate /etc/swanctl/conf.d/secrets.conf

        Contains EAP credentials for each active client.
        """
        secrets = '''# ProxyGate EAP secrets
# Auto-generated - DO NOT EDIT MANUALLY

secrets {
    private-server {
        file = privkey.pem
    }
'''

        for client in clients:
            if client.is_active:
                secrets += f'''
    eap-{client.username} {{
        id = {client.username}
        secret = "{client.password}"
    }}
'''

        secrets += "}\n"
        return secrets

    def write_config(self, clients: List[VpnClient]) -> None:
        """Write configuration files."""
        # Write connections.conf
        connections = self.generate_connections_conf()
        with open(self.CONNECTIONS_FILE, 'w') as f:
            f.write(connections)

        # Write secrets.conf
        secrets = self.generate_secrets_conf(clients)
        with open(self.SECRETS_FILE, 'w') as f:
            f.write(secrets)

    def reload(self) -> bool:
        """
        Reload strongSwan configuration.

        Uses: swanctl --load-all
        This picks up changes without disconnecting existing clients.
        """
        try:
            subprocess.run(
                ["swanctl", "--load-all"],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to reload strongSwan: {e.stderr}")
            return False
        except FileNotFoundError:
            print("swanctl not found - strongSwan may not be installed")
            return False

    def terminate_client(self, username: str) -> bool:
        """
        Force disconnect a client.

        Uses: swanctl --terminate --ike <sa-name>
        """
        try:
            # Find SA by identity
            result = subprocess.run(
                ["swanctl", "--list-sas"],
                capture_output=True,
                text=True
            )

            # Parse output to find SA for this user
            # This is a simplified version - real implementation would need proper parsing
            subprocess.run(
                ["swanctl", "--terminate", "--ike", f"proxygate-{username}"],
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
        except FileNotFoundError:
            return False

    def get_active_sessions(self) -> List[Dict]:
        """
        Get list of active VPN sessions.

        Uses: swanctl --list-sas
        """
        try:
            result = subprocess.run(
                ["swanctl", "--list-sas"],
                capture_output=True,
                text=True,
                check=True
            )

            # Parse output (simplified)
            sessions = []
            # Real implementation would parse the swanctl output format
            return sessions

        except subprocess.CalledProcessError:
            return []
        except FileNotFoundError:
            return []

    def add_client(self, username: str, password: str, all_clients: List[VpnClient]) -> bool:
        """Add a new client and reload config."""
        self.write_config(all_clients)
        return self.reload()

    def remove_client(self, username: str, all_clients: List[VpnClient]) -> bool:
        """Remove a client, disconnect them, and reload config."""
        self.terminate_client(username)
        self.write_config(all_clients)
        return self.reload()

    def change_password(self, username: str, new_password: str, all_clients: List[VpnClient]) -> bool:
        """Change client password and reload config."""
        self.write_config(all_clients)
        return self.reload()
