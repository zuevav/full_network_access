from typing import List
from app.config import settings


class PacGenerator:
    """Generates PAC (Proxy Auto-Config) files for clients."""

    def generate(self, domains: List[str], username: str = "") -> str:
        """
        Generate a PAC file for the given domains.

        Args:
            domains: List of domains that should go through proxy
            username: Client username for the comment

        Returns:
            PAC file content as string
        """
        if not domains:
            return self._generate_direct_only()

        domain_checks = []
        for domain in domains:
            domain = domain.lower().strip()
            # Check exact domain and subdomains
            domain_checks.append(f'dnsDomainIs(host, ".{domain}")')
            domain_checks.append(f'host === "{domain}"')

        conditions = " ||\n        ".join(domain_checks)

        pac = f'''// ProxyGate PAC File
// Client: {username}
// Proxy: {settings.vps_public_ip}:{settings.proxy_http_port}

function FindProxyForURL(url, host) {{
    // Lowercase host for comparison
    host = host.toLowerCase();

    // Check if host matches configured domains
    if ({conditions}) {{
        return "PROXY {settings.vps_public_ip}:{settings.proxy_http_port}; SOCKS5 {settings.vps_public_ip}:{settings.proxy_socks_port}; DIRECT";
    }}

    // All other traffic goes directly
    return "DIRECT";
}}
'''
        return pac

    def _generate_direct_only(self) -> str:
        """Generate a PAC file that routes everything directly."""
        return '''// ProxyGate PAC File - No domains configured
function FindProxyForURL(url, host) {
    return "DIRECT";
}
'''
