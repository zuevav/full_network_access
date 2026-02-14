import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from app.config import settings
from app.services.domain_resolver import DomainResolver
from app.api.system import get_configured_domain, get_configured_server_ip, get_configured_ports

if TYPE_CHECKING:
    from app.models import Client


class ProfileGenerator:
    """Generates VPN/Proxy profiles for all platforms."""

    def __init__(self):
        self.resolver = DomainResolver()

    def _get_client_routes(self, client: "Client") -> list[str]:
        """Get routes for a client from their domains."""
        if client.vpn_config and client.vpn_config.resolved_routes:
            return json.loads(client.vpn_config.resolved_routes)

        # Resolve domains to CIDRs
        routes = []
        for domain in client.domains:
            if domain.is_active:
                routes.extend(self.resolver.resolve_domain(domain.domain))

        return list(set(routes))

    def _get_client_domains(self, client: "Client") -> list[str]:
        """Get list of active domains for a client (for VPN On Demand)."""
        domains = []
        for d in client.domains:
            if d.is_active:
                # Use wildcard only - covers base domain and all subdomains
                domains.append(f"*.{d.domain}")
        return domains

    def generate_windows_ps1(self, client: "Client") -> str:
        """Generate Windows PowerShell script for VPN setup."""
        routes = self._get_client_routes(client)
        domain = get_configured_domain()

        routes_commands = "\n".join([
            f'Add-VpnConnectionRoute -ConnectionName $VpnName -DestinationPrefix "{route}" -PassThru | Out-Null'
            for route in routes
        ])

        script = f'''# ============================================
# ZETIT FNA - Windows VPN Setup
# Client: {client.name}
# Date: {datetime.now().strftime("%Y-%m-%d")}
# ============================================
# Run this script as Administrator!
# Right-click -> "Run as administrator"
# ============================================

$ErrorActionPreference = "Stop"
$VpnName = "ZETIT FNA"
$ServerAddress = "{domain}"
$Username = "{client.vpn_config.username}"

Write-Host "=== ZETIT FNA Setup ===" -ForegroundColor Cyan
Write-Host ""

# Remove existing connection
try {{
    Remove-VpnConnection -Name $VpnName -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Old connection removed" -ForegroundColor Yellow
}} catch {{}}

# Create VPN connection (IKEv2)
Write-Host "[1/4] Creating VPN connection..." -ForegroundColor Green
Add-VpnConnection `
    -Name $VpnName `
    -ServerAddress $ServerAddress `
    -TunnelType Ikev2 `
    -AuthenticationMethod Eap `
    -EncryptionLevel Required `
    -SplitTunneling `
    -RememberCredential `
    -DnsSuffix ""

# Configure IPsec
Write-Host "[2/4] Configuring encryption..." -ForegroundColor Green
Set-VpnConnectionIPsecConfiguration -ConnectionName $VpnName `
    -AuthenticationTransformConstants SHA256128 `
    -CipherTransformConstants AES256 `
    -DHGroup Group14 `
    -IntegrityCheckMethod SHA256 `
    -PfsGroup PFS2048 `
    -EncryptionMethod AES256 `
    -Force

# Add routes for your services
Write-Host "[3/4] Adding routes..." -ForegroundColor Green

{routes_commands}

# Save credentials
Write-Host "[4/4] Configuring credentials..." -ForegroundColor Green
cmdkey /generic:$ServerAddress /user:$Username

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " VPN configured successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " Connect: Settings > Network > VPN > $VpnName"
Write-Host " Username: $Username"
Write-Host " Password: (enter on first connection)"
Write-Host ""
Write-Host " Traffic routed through VPN:"
Write-Host "   - Your configured domains"
Write-Host " Other traffic goes directly."
Write-Host ""
Read-Host "Press Enter to exit"
'''
        return script

    def generate_ios_mobileconfig(self, client: "Client", mode: str = "ondemand") -> bytes:
        """
        Generate iOS .mobileconfig profile with different VPN modes.

        Modes:
        - ondemand: VPN connects only when accessing listed domains (recommended)
        - always: VPN always connected, split tunneling by IP routes
        - full: VPN always connected, ALL traffic through VPN
        """
        routes = self._get_client_routes(client)
        client_domains = self._get_client_domains(client)
        server_domain = get_configured_domain()

        profile_uuid = str(uuid.uuid4()).upper()
        vpn_uuid = str(uuid.uuid4()).upper()

        # Routes XML for split tunneling
        routes_xml = "\n".join([
            self._cidr_to_route_dict(route) for route in routes
        ])

        # Domains XML for on-demand rules
        domains_xml = "\n".join([
            f"                        <string>{d}</string>" for d in client_domains
        ])

        # Profile name based on mode
        mode_names = {
            "ondemand": "ZETIT FNA (Auto)",
            "always": "ZETIT FNA (Split)",
            "full": "ZETIT FNA (Full)"
        }
        profile_name = mode_names.get(mode, "ZETIT FNA")

        # IPv4 configuration based on mode
        if mode == "full":
            ipv4_config = """
            <key>IPv4</key>
            <dict>
                <key>OverridePrimary</key>
                <integer>1</integer>
            </dict>"""
        else:
            ipv4_config = f"""
            <key>IPv4</key>
            <dict>
                <key>OverridePrimary</key>
                <integer>0</integer>
                <key>IncludedRoutes</key>
                <array>
{routes_xml}
                </array>
            </dict>"""

        # OnDemand rules based on mode
        if mode == "ondemand":
            ondemand_config = f"""
            <key>OnDemandEnabled</key>
            <integer>1</integer>
            <key>OnDemandRules</key>
            <array>
                <dict>
                    <key>Action</key>
                    <string>EvaluateConnection</string>
                    <key>ActionParameters</key>
                    <array>
                        <dict>
                            <key>Domains</key>
                            <array>
{domains_xml}
                            </array>
                            <key>DomainAction</key>
                            <string>ConnectIfNeeded</string>
                        </dict>
                    </array>
                </dict>
                <dict>
                    <key>Action</key>
                    <string>Disconnect</string>
                </dict>
            </array>"""
        else:
            # always or full - keep VPN connected
            ondemand_config = """
            <key>OnDemandEnabled</key>
            <integer>1</integer>
            <key>OnDemandRules</key>
            <array>
                <dict>
                    <key>Action</key>
                    <string>Connect</string>
                </dict>
            </array>"""

        config = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>PayloadType</key>
            <string>com.apple.vpn.managed</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>PayloadIdentifier</key>
            <string>com.zetit.fna.vpn.{client.id}.{mode}</string>
            <key>PayloadUUID</key>
            <string>{vpn_uuid}</string>
            <key>PayloadDisplayName</key>
            <string>{profile_name}</string>

            <key>UserDefinedName</key>
            <string>{profile_name}</string>
            <key>VPNType</key>
            <string>IKEv2</string>

            <key>IKEv2</key>
            <dict>
                <key>RemoteAddress</key>
                <string>{server_domain}</string>
                <key>RemoteIdentifier</key>
                <string>{server_domain}</string>
                <key>LocalIdentifier</key>
                <string>{client.vpn_config.username}</string>

                <key>AuthenticationMethod</key>
                <string>None</string>
                <key>ExtendedAuthEnabled</key>
                <true/>
                <key>AuthName</key>
                <string>{client.vpn_config.username}</string>
                <key>AuthPassword</key>
                <string>{client.vpn_config.password}</string>

                <key>IKESecurityAssociationParameters</key>
                <dict>
                    <key>EncryptionAlgorithm</key>
                    <string>AES-256</string>
                    <key>IntegrityAlgorithm</key>
                    <string>SHA2-256</string>
                    <key>DiffieHellmanGroup</key>
                    <integer>14</integer>
                </dict>
                <key>ChildSecurityAssociationParameters</key>
                <dict>
                    <key>EncryptionAlgorithm</key>
                    <string>AES-256</string>
                    <key>IntegrityAlgorithm</key>
                    <string>SHA2-256</string>
                    <key>DiffieHellmanGroup</key>
                    <integer>14</integer>
                </dict>

                <key>EnablePFS</key>
                <true/>
            </dict>
{ipv4_config}
{ondemand_config}
        </dict>
    </array>

    <key>PayloadDisplayName</key>
    <string>{profile_name} - {client.name}</string>
    <key>PayloadIdentifier</key>
    <string>com.zetit.fna.profile.{client.id}.{mode}</string>
    <key>PayloadOrganization</key>
    <string>ZETIT</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>{profile_uuid}</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
    <key>PayloadRemovalDisallowed</key>
    <false/>
</dict>
</plist>'''
        return config.encode('utf-8')

    def generate_macos_mobileconfig(self, client: "Client", mode: str = "ondemand") -> bytes:
        """Generate macOS .mobileconfig profile."""
        # macOS uses the same format as iOS
        return self.generate_ios_mobileconfig(client, mode=mode)

    def generate_android_sswan(self, client: "Client") -> bytes:
        """Generate Android strongSwan .sswan profile."""
        routes = self._get_client_routes(client)
        domain = get_configured_domain()

        profile = {
            "uuid": str(uuid.uuid4()),
            "name": "ZETIT FNA",
            "type": "ikev2-eap",
            "remote": {
                "addr": domain,
                "id": domain
            },
            "local": {
                "eap_id": client.vpn_config.username
            },
            "split-tunneling": {
                "subnets": routes
            }
        }

        return json.dumps(profile, indent=2).encode('utf-8')

    def generate_pac_file(self, client: "Client") -> str:
        """Generate PAC file for proxy auto-configuration."""
        domains = [d.domain for d in client.domains if d.is_active]
        proxy_host = get_configured_domain()
        http_port, _ = get_configured_ports()

        domain_checks = []
        for domain in domains:
            domain_checks.append(f'dnsDomainIs(host, ".{domain}")')
            domain_checks.append(f'host === "{domain}"')

        conditions = " ||\n        ".join(domain_checks)

        pac = f'''// PAC: {client.vpn_config.username if client.vpn_config else client.name}
// Generated by ZETIT FNA
function FindProxyForURL(url, host) {{
    if ({conditions}) {{
        return "HTTPS {proxy_host}:2053; HTTPS {proxy_host}:443; PROXY {proxy_host}:3128; DIRECT";
    }}
    return "DIRECT";
}}
'''
        return pac

    def _cidr_to_route_dict(self, cidr: str) -> str:
        """Convert CIDR to iOS route dict XML."""
        import ipaddress
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            address = str(network.network_address)
            mask = str(network.netmask)
            return f'''                    <dict>
                        <key>Address</key>
                        <string>{address}</string>
                        <key>SubnetMask</key>
                        <string>{mask}</string>
                    </dict>'''
        except ValueError:
            return ""
