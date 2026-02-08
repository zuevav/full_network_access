from datetime import datetime, timedelta, timezone
from typing import Optional, Literal
import secrets
import string

from jose import JWTError, jwt
from passlib.context import CryptContext
import pyotp

from app.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


def generate_password(length: int = 16) -> str:
    """Generate a random password."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_access_token() -> str:
    """Generate a random access token (UUID-like)."""
    return secrets.token_hex(32)


def create_access_token(
    data: dict,
    token_type: Literal["admin", "client"] = "admin",
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        if token_type == "admin":
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        else:
            expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)

    to_encode.update({
        "exp": expire,
        "type": token_type,
        "iat": datetime.now(timezone.utc)
    })

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


def verify_totp(secret: str, code: str) -> bool:
    """Verify TOTP code."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code)


def generate_totp_secret() -> str:
    """Generate new TOTP secret."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str) -> str:
    """Get TOTP provisioning URI for QR code."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name="ProxyGate")


def is_access_token_expired(client) -> bool:
    """Check if client's access token has expired. NULL = never expires."""
    if client.access_token_expires_at is None:
        return False
    return datetime.now(timezone.utc) > client.access_token_expires_at.replace(tzinfo=timezone.utc)
