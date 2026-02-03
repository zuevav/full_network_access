import ipaddress
from typing import List, Dict, Set


class DomainResolver:
    """Resolves domains to CIDR blocks for VPN routing."""

    # Pre-defined CIDRs for popular services
    # (DNS resolution is unreliable for CDN-hosted services)
    KNOWN_CIDRS: Dict[str, List[str]] = {
        # AI Services
        "openai.com": ["104.18.0.0/16", "172.64.0.0/13"],
        "chatgpt.com": ["104.18.0.0/16", "172.64.0.0/13"],
        "oaiusercontent.com": ["104.18.0.0/16", "172.64.0.0/13"],
        "claude.ai": ["104.18.0.0/16", "172.64.0.0/13"],
        "anthropic.com": ["104.18.0.0/16", "172.64.0.0/13"],
        "perplexity.ai": ["104.18.0.0/16", "172.64.0.0/13"],

        # Google
        "google.com": ["142.250.0.0/15", "172.217.0.0/16", "216.58.192.0/19",
                       "172.253.0.0/16", "74.125.0.0/16", "173.194.0.0/16"],
        "googleapis.com": ["142.250.0.0/15", "172.217.0.0/16", "172.253.0.0/16"],
        "gstatic.com": ["142.250.0.0/15", "172.217.0.0/16"],
        "googleusercontent.com": ["142.250.0.0/15", "172.217.0.0/16"],
        "youtube.com": ["142.250.0.0/15", "172.217.0.0/16", "216.58.192.0/19",
                        "172.253.0.0/16", "74.125.0.0/16"],
        "googlevideo.com": ["142.250.0.0/15", "172.217.0.0/16", "172.253.0.0/16"],
        "ytimg.com": ["142.250.0.0/15", "172.217.0.0/16"],
        "ggpht.com": ["142.250.0.0/15", "172.217.0.0/16"],

        # Netflix
        "netflix.com": ["23.246.0.0/18", "37.77.184.0/21", "45.57.0.0/17",
                        "64.120.128.0/17", "108.175.32.0/20", "185.2.220.0/22",
                        "185.9.188.0/22", "192.173.64.0/18", "198.38.96.0/19",
                        "198.45.48.0/20"],
        "nflxvideo.net": ["23.246.0.0/18", "45.57.0.0/17", "185.2.220.0/22"],
        "nflxext.com": ["23.246.0.0/18", "45.57.0.0/17"],
        "nflximg.net": ["23.246.0.0/18", "45.57.0.0/17"],

        # Meta / Facebook
        "facebook.com": ["157.240.0.0/16", "31.13.24.0/21", "31.13.64.0/18",
                         "179.60.192.0/22", "185.60.216.0/22"],
        "fbcdn.net": ["157.240.0.0/16", "31.13.24.0/21"],
        "fb.com": ["157.240.0.0/16", "31.13.24.0/21"],
        "instagram.com": ["157.240.0.0/16", "31.13.24.0/21", "31.13.64.0/18"],
        "cdninstagram.com": ["157.240.0.0/16", "31.13.24.0/21"],

        # Twitter / X
        "twitter.com": ["104.244.42.0/24", "104.244.46.0/24", "199.16.156.0/22",
                        "199.59.148.0/22"],
        "x.com": ["104.244.42.0/24", "104.244.46.0/24", "199.16.156.0/22"],
        "twimg.com": ["104.244.42.0/24", "199.16.156.0/22"],
        "t.co": ["104.244.42.0/24"],

        # LinkedIn
        "linkedin.com": ["108.174.0.0/20", "144.2.0.0/16"],
        "licdn.com": ["108.174.0.0/20", "144.2.0.0/16"],

        # GitHub
        "github.com": ["140.82.112.0/20", "185.199.108.0/22", "192.30.252.0/22",
                       "143.55.64.0/20"],
        "github.io": ["185.199.108.0/22"],
        "githubusercontent.com": ["185.199.108.0/22"],
        "githubassets.com": ["185.199.108.0/22"],

        # Spotify
        "spotify.com": ["35.186.224.0/20", "78.31.8.0/21", "194.132.196.0/22"],
        "spotifycdn.com": ["35.186.224.0/20", "78.31.8.0/21"],
        "scdn.co": ["35.186.224.0/20", "78.31.8.0/21"],

        # Discord
        "discord.com": ["162.159.0.0/16"],
        "discord.gg": ["162.159.0.0/16"],
        "discordapp.com": ["162.159.0.0/16"],

        # TikTok
        "tiktok.com": ["16.0.0.0/8", "34.0.0.0/8", "99.0.0.0/8"],
        "tiktokcdn.com": ["16.0.0.0/8", "34.0.0.0/8"],

        # Common CDNs (Cloudflare)
        "cloudflare.com": ["104.16.0.0/12", "172.64.0.0/13", "131.0.72.0/22"],
    }

    # Default CIDR for unknown domains
    DEFAULT_CIDRS = ["104.16.0.0/12", "172.64.0.0/13"]  # Cloudflare ranges

    def resolve_domain(self, domain: str, include_subdomains: bool = True) -> List[str]:
        """
        Resolve a domain to list of CIDRs.

        Strategy:
        1. Check KNOWN_CIDRS for pre-defined mappings
        2. If not found, use default CDN ranges

        Returns list of CIDR strings.
        """
        domain = domain.lower().strip()

        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]

        # Check known CIDRs
        if domain in self.KNOWN_CIDRS:
            return self.KNOWN_CIDRS[domain]

        # Check if it's a subdomain of a known domain
        for known_domain, cidrs in self.KNOWN_CIDRS.items():
            if domain.endswith(f".{known_domain}"):
                return cidrs

        # Return default CDN ranges for unknown domains
        return self.DEFAULT_CIDRS

    def resolve_domains(self, domains: List[str]) -> List[str]:
        """Resolve multiple domains and return unique CIDRs."""
        all_cidrs: Set[str] = set()

        for domain in domains:
            cidrs = self.resolve_domain(domain)
            all_cidrs.update(cidrs)

        return self.optimize_routes(list(all_cidrs))

    def optimize_routes(self, cidrs: List[str]) -> List[str]:
        """
        Optimize route list:
        1. Remove duplicates
        2. Merge overlapping CIDRs
        3. Sort by network address
        """
        if not cidrs:
            return []

        networks = []
        for cidr in cidrs:
            try:
                networks.append(ipaddress.ip_network(cidr, strict=False))
            except ValueError:
                continue

        # Collapse overlapping networks
        collapsed = list(ipaddress.collapse_addresses(networks))

        # Sort and convert back to strings
        return sorted([str(net) for net in collapsed])
