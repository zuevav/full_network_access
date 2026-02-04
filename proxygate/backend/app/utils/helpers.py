from typing import Optional, Set
from datetime import date, datetime
import re


# Russian to Latin transliteration map
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
    'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
    'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
    'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
    'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
}


def transliterate(text: str) -> str:
    """Transliterate Russian text to Latin."""
    result = []
    for char in text:
        if char in TRANSLIT_MAP:
            result.append(TRANSLIT_MAP[char])
        else:
            result.append(char)
    return ''.join(result)


def generate_username(client_id: int, name: str = "", existing_usernames: Optional[Set[str]] = None) -> str:
    """
    Generate VPN/Proxy username from client name.
    Falls back to client_XXX format if name is empty or invalid.

    Args:
        client_id: Client ID (used as fallback)
        name: Client name (will be transliterated if Russian)
        existing_usernames: Set of existing usernames to avoid duplicates
    """
    if existing_usernames is None:
        existing_usernames = set()

    # Try to generate from name
    if name and name.strip():
        # Transliterate Russian
        base = transliterate(name.strip())
        # Keep only alphanumeric chars, convert to lowercase
        base = re.sub(r'[^a-zA-Z0-9]', '', base).lower()

        # If we got a valid base name
        if base and len(base) >= 2:
            # Try without number first
            if base not in existing_usernames:
                return base

            # Add numbers until unique
            for i in range(1, 1000):
                candidate = f"{base}{i}"
                if candidate not in existing_usernames:
                    return candidate

    # Fallback to client_XXX format
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
