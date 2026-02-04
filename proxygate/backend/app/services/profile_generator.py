import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from app.config import settings
from app.services.domain_resolver import DomainResolver

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

    def generate_windows_ps1(self, client: "Client") -> str:
        """Generate Windows PowerShell script for VPN setup."""
        routes = self._get_client_routes(client)

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
$ServerAddress = "{settings.vps_domain}"
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

    def generate_ios_mobileconfig(self, client: "Client") -> bytes:
        """Generate iOS .mobileconfig profile."""
        routes = self._get_client_routes(client)

        profile_uuid = str(uuid.uuid4()).upper()
        vpn_uuid = str(uuid.uuid4()).upper()

        routes_xml = "\n".join([
            self._cidr_to_route_dict(route) for route in routes
        ])

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
            <string>com.zetit.fna.vpn.{client.id}</string>
            <key>PayloadUUID</key>
            <string>{vpn_uuid}</string>
            <key>PayloadDisplayName</key>
            <string>ZETIT FNA</string>

            <key>UserDefinedName</key>
            <string>ZETIT FNA</string>
            <key>VPNType</key>
            <string>IKEv2</string>

            <key>IKEv2</key>
            <dict>
                <key>RemoteAddress</key>
                <string>{settings.vps_domain}</string>
                <key>RemoteIdentifier</key>
                <string>{settings.ikev2_server_id}</string>
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

            <key>IPv4</key>
            <dict>
                <key>OverridePrimary</key>
                <integer>0</integer>
                <key>IncludedRoutes</key>
                <array>
{routes_xml}
                </array>
            </dict>

            <key>OnDemandEnabled</key>
            <integer>1</integer>
            <key>OnDemandRules</key>
            <array>
                <dict>
                    <key>Action</key>
                    <string>Connect</string>
                </dict>
            </array>
        </dict>
    </array>

    <key>PayloadDisplayName</key>
    <string>ZETIT FNA - {client.name}</string>
    <key>PayloadIdentifier</key>
    <string>com.zetit.fna.profile.{client.id}</string>
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

    def generate_macos_mobileconfig(self, client: "Client") -> bytes:
        """Generate macOS .mobileconfig profile."""
        # macOS uses the same format as iOS
        return self.generate_ios_mobileconfig(client)

    def generate_android_sswan(self, client: "Client") -> bytes:
        """Generate Android strongSwan .sswan profile."""
        routes = self._get_client_routes(client)

        profile = {
            "uuid": str(uuid.uuid4()),
            "name": "ZETIT FNA",
            "type": "ikev2-eap",
            "remote": {
                "addr": settings.vps_domain,
                "id": settings.ikev2_server_id
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

        domain_checks = []
        for domain in domains:
            domain_checks.append(f'dnsDomainIs(host, ".{domain}")')
            domain_checks.append(f'host === "{domain}"')

        conditions = " ||\n        ".join(domain_checks)

        pac = f'''// PAC: {client.vpn_config.username if client.vpn_config else client.name}
// Generated by ZETIT FNA
function FindProxyForURL(url, host) {{
    if ({conditions}) {{
        return "PROXY {settings.vps_public_ip}:{settings.proxy_http_port}; DIRECT";
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
