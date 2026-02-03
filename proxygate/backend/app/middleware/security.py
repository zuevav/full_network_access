"""
Security middleware for brute force protection
"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select
from datetime import datetime

from app.database import async_session_maker
from app.models.security import BlockedIP


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware to check if IP is blocked"""

    # Endpoints to protect
    PROTECTED_ENDPOINTS = [
        "/api/auth/login",
        "/api/portal/auth/login",
        "/api/portal/auth"
    ]

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check if this is a protected endpoint
        if any(request.url.path.startswith(ep) for ep in self.PROTECTED_ENDPOINTS):
            # Check if IP is blocked
            is_blocked, block_info = await self._check_blocked(client_ip)

            if is_blocked:
                if block_info.is_permanent:
                    detail = f"IP заблокирован: {block_info.reason}"
                else:
                    remaining = block_info.blocked_until - datetime.utcnow()
                    minutes = int(remaining.total_seconds() / 60)
                    detail = f"IP временно заблокирован. Осталось: {minutes} мин. Причина: {block_info.reason}"

                raise HTTPException(status_code=403, detail=detail)

        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get real client IP, considering proxies"""
        # Check X-Forwarded-For header (for reverse proxies like nginx)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP in the list (original client)
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct connection IP
        if request.client:
            return request.client.host

        return "unknown"

    async def _check_blocked(self, ip_address: str) -> tuple[bool, BlockedIP | None]:
        """Check if IP is blocked"""
        async with async_session_maker() as db:
            result = await db.execute(
                select(BlockedIP).where(
                    BlockedIP.ip_address == ip_address,
                    BlockedIP.is_active == True
                )
            )
            block = result.scalar_one_or_none()

            if not block:
                return False, None

            # Check if temporary block has expired
            if not block.is_permanent and block.blocked_until:
                if datetime.utcnow() > block.blocked_until:
                    # Auto-unblock expired temporary blocks
                    block.is_active = False
                    block.unblocked_at = datetime.utcnow()
                    block.notes = "Auto-unblocked: temporary block expired"
                    await db.commit()
                    return False, None

            return True, block


def get_client_ip(request: Request) -> str:
    """Utility function to get client IP from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    if request.client:
        return request.client.host

    return "unknown"
