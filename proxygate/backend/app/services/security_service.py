"""
Security service for brute force protection
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security import FailedLogin, BlockedIP, SecurityEvent
from app.config import settings


class SecurityService:
    """Handles brute force protection and security events"""

    # Configuration
    MAX_FAILED_ATTEMPTS = 5  # Block after this many failures
    BLOCK_DURATION_MINUTES = 30  # Temporary block duration
    ATTEMPT_WINDOW_MINUTES = 15  # Count attempts within this window
    PERMANENT_BLOCK_THRESHOLD = 3  # Permanent block after this many temp blocks

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_failed_attempt(
        self,
        ip_address: str,
        username: Optional[str] = None,
        endpoint: str = "/api/auth/login",
        user_agent: Optional[str] = None
    ) -> Optional[BlockedIP]:
        """
        Record a failed login attempt and check if IP should be blocked.
        Returns BlockedIP if the IP was blocked, None otherwise.
        """
        # Record the failed attempt
        failed_login = FailedLogin(
            ip_address=ip_address,
            username=username,
            endpoint=endpoint,
            user_agent=user_agent
        )
        self.db.add(failed_login)

        # Log security event
        await self._log_event(
            "login_failed",
            ip_address=ip_address,
            username=username,
            details=f"Failed login attempt on {endpoint}"
        )

        # Count recent failed attempts from this IP
        window_start = datetime.utcnow() - timedelta(minutes=self.ATTEMPT_WINDOW_MINUTES)
        result = await self.db.execute(
            select(func.count(FailedLogin.id))
            .where(FailedLogin.ip_address == ip_address)
            .where(FailedLogin.attempt_time >= window_start)
        )
        attempt_count = result.scalar() or 0

        # Check if we should block
        if attempt_count >= self.MAX_FAILED_ATTEMPTS:
            return await self._block_ip(ip_address, attempt_count)

        await self.db.commit()
        return None

    async def _block_ip(self, ip_address: str, failed_attempts: int) -> BlockedIP:
        """Block an IP address"""
        # Check if already blocked
        result = await self.db.execute(
            select(BlockedIP).where(
                BlockedIP.ip_address == ip_address,
                BlockedIP.is_active == True
            )
        )
        existing_block = result.scalar_one_or_none()

        if existing_block:
            # Update existing block
            existing_block.failed_attempts += failed_attempts
            existing_block.blocked_at = datetime.utcnow()

            # Check if should become permanent
            if existing_block.failed_attempts >= self.MAX_FAILED_ATTEMPTS * self.PERMANENT_BLOCK_THRESHOLD:
                existing_block.is_permanent = True
                existing_block.blocked_until = None
                existing_block.reason = "Permanent block: repeated brute force attempts"
            else:
                existing_block.blocked_until = datetime.utcnow() + timedelta(minutes=self.BLOCK_DURATION_MINUTES)

            await self._log_event(
                "ip_block_extended",
                ip_address=ip_address,
                details=f"Block extended. Total attempts: {existing_block.failed_attempts}"
            )

            await self.db.commit()
            return existing_block

        # Create new block
        blocked_ip = BlockedIP(
            ip_address=ip_address,
            reason=f"Too many failed login attempts ({failed_attempts} attempts)",
            failed_attempts=failed_attempts,
            blocked_until=datetime.utcnow() + timedelta(minutes=self.BLOCK_DURATION_MINUTES),
            is_permanent=False
        )
        self.db.add(blocked_ip)

        await self._log_event(
            "ip_blocked",
            ip_address=ip_address,
            details=f"IP blocked for {self.BLOCK_DURATION_MINUTES} minutes after {failed_attempts} failed attempts"
        )

        await self.db.commit()
        return blocked_ip

    async def is_ip_blocked(self, ip_address: str) -> tuple[bool, Optional[BlockedIP]]:
        """Check if an IP is currently blocked"""
        result = await self.db.execute(
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
                await self.db.commit()
                return False, None

        return True, block

    async def unblock_ip(self, ip_address: str, admin_username: str, notes: Optional[str] = None) -> bool:
        """Manually unblock an IP"""
        result = await self.db.execute(
            select(BlockedIP).where(
                BlockedIP.ip_address == ip_address,
                BlockedIP.is_active == True
            )
        )
        block = result.scalar_one_or_none()

        if not block:
            return False

        block.is_active = False
        block.unblocked_at = datetime.utcnow()
        block.unblocked_by = admin_username
        block.notes = notes or f"Manually unblocked by {admin_username}"

        await self._log_event(
            "ip_unblocked",
            ip_address=ip_address,
            username=admin_username,
            details=f"IP unblocked by admin: {notes or 'No reason provided'}"
        )

        await self.db.commit()
        return True

    async def block_ip_manually(
        self,
        ip_address: str,
        admin_username: str,
        reason: str,
        is_permanent: bool = True,
        duration_minutes: Optional[int] = None
    ) -> BlockedIP:
        """Manually block an IP (by admin)"""
        # Check if already blocked
        result = await self.db.execute(
            select(BlockedIP).where(
                BlockedIP.ip_address == ip_address,
                BlockedIP.is_active == True
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.reason = reason
            existing.is_permanent = is_permanent
            if not is_permanent and duration_minutes:
                existing.blocked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
            else:
                existing.blocked_until = None
            existing.notes = f"Manually blocked by {admin_username}"
            await self.db.commit()
            return existing

        blocked_until = None
        if not is_permanent and duration_minutes:
            blocked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)

        blocked_ip = BlockedIP(
            ip_address=ip_address,
            reason=reason,
            is_permanent=is_permanent,
            blocked_until=blocked_until,
            notes=f"Manually blocked by {admin_username}"
        )
        self.db.add(blocked_ip)

        await self._log_event(
            "ip_blocked_manual",
            ip_address=ip_address,
            username=admin_username,
            details=f"Manually blocked: {reason}"
        )

        await self.db.commit()
        return blocked_ip

    async def get_blocked_ips(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> list[BlockedIP]:
        """Get list of blocked IPs"""
        query = select(BlockedIP).order_by(BlockedIP.blocked_at.desc())

        if active_only:
            query = query.where(BlockedIP.is_active == True)

        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_blocked_ip_count(self, active_only: bool = True) -> int:
        """Get count of blocked IPs"""
        query = select(func.count(BlockedIP.id))
        if active_only:
            query = query.where(BlockedIP.is_active == True)
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def get_recent_failed_attempts(
        self,
        ip_address: Optional[str] = None,
        limit: int = 100
    ) -> list[FailedLogin]:
        """Get recent failed login attempts"""
        query = select(FailedLogin).order_by(FailedLogin.attempt_time.desc())

        if ip_address:
            query = query.where(FailedLogin.ip_address == ip_address)

        query = query.limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_security_events(
        self,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> list[SecurityEvent]:
        """Get security events log"""
        query = select(SecurityEvent).order_by(SecurityEvent.created_at.desc())

        if event_type:
            query = query.where(SecurityEvent.event_type == event_type)

        query = query.limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def record_successful_login(self, ip_address: str, username: str):
        """Record successful login (clears failed attempts for this IP)"""
        # Clear recent failed attempts
        window_start = datetime.utcnow() - timedelta(minutes=self.ATTEMPT_WINDOW_MINUTES)
        await self.db.execute(
            delete(FailedLogin).where(
                FailedLogin.ip_address == ip_address,
                FailedLogin.attempt_time >= window_start
            )
        )

        await self._log_event(
            "login_success",
            ip_address=ip_address,
            username=username,
            details="Successful login"
        )

        await self.db.commit()

    async def cleanup_old_records(self, days: int = 30):
        """Clean up old failed login records and events"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        await self.db.execute(
            delete(FailedLogin).where(FailedLogin.attempt_time < cutoff)
        )
        await self.db.execute(
            delete(SecurityEvent).where(SecurityEvent.created_at < cutoff)
        )

        await self.db.commit()

    async def _log_event(
        self,
        event_type: str,
        ip_address: Optional[str] = None,
        username: Optional[str] = None,
        details: Optional[str] = None
    ):
        """Log a security event"""
        event = SecurityEvent(
            event_type=event_type,
            ip_address=ip_address,
            username=username,
            details=details
        )
        self.db.add(event)


# Dependency for FastAPI
async def get_security_service(db: AsyncSession) -> SecurityService:
    return SecurityService(db)
