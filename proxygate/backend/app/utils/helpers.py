from typing import Optional
from datetime import date, datetime


def generate_username(client_id: int) -> str:
    """Generate VPN/Proxy username from client ID."""
    return f"client_{client_id:03d}"


def get_subscription_status(valid_until: Optional[date]) -> tuple[str, Optional[int]]:
    """
    Get subscription status and days left.
    Returns: (status, days_left)
    Status: "active" | "expiring" | "expired" | "none"
    """
    if valid_until is None:
        return ("none", None)

    today = date.today()
    days_left = (valid_until - today).days

    if days_left < 0:
        return ("expired", days_left)
    elif days_left <= 7:
        return ("expiring", days_left)
    else:
        return ("active", days_left)


def format_date_range(valid_from: date, valid_until: date) -> str:
    """Format date range as string."""
    return f"{valid_from.strftime('%d.%m')} - {valid_until.strftime('%d.%m.%Y')}"


def normalize_domain(domain: str) -> str:
    """Normalize domain name (lowercase, strip whitespace)."""
    domain = domain.lower().strip()
    # Remove protocol if present
    if domain.startswith("http://"):
        domain = domain[7:]
    elif domain.startswith("https://"):
        domain = domain[8:]
    # Remove path
    domain = domain.split("/")[0]
    # Remove www. prefix
    if domain.startswith("www."):
        domain = domain[4:]
    return domain
