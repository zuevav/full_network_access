"""
Security API endpoints - brute force protection management
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_admin
from app.models.admin import AdminUser
from app.models.security import BlockedIP, FailedLogin, SecurityEvent
from app.schemas.security import (
    BlockedIPResponse,
    BlockedIPCreate,
    BlockedIPListResponse,
    UnblockIPRequest,
    FailedLoginResponse,
    SecurityEventResponse,
    SecurityStatsResponse
)
from app.services.security_service import SecurityService

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/stats", response_model=SecurityStatsResponse)
async def get_security_stats(
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get security statistics for dashboard"""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = now - timedelta(hours=24)

    # Active blocks
    result = await db.execute(
        select(func.count(BlockedIP.id)).where(BlockedIP.is_active == True)
    )
    active_blocks = result.scalar() or 0

    # Total blocks (all time)
    result = await db.execute(select(func.count(BlockedIP.id)))
    total_blocks = result.scalar() or 0

    # Failed attempts in last 24h
    result = await db.execute(
        select(func.count(FailedLogin.id)).where(FailedLogin.attempt_time >= yesterday)
    )
    failed_attempts_24h = result.scalar() or 0

    # Blocked today
    result = await db.execute(
        select(func.count(BlockedIP.id)).where(BlockedIP.blocked_at >= today_start)
    )
    blocked_today = result.scalar() or 0

    # Security events today
    result = await db.execute(
        select(func.count(SecurityEvent.id)).where(SecurityEvent.created_at >= today_start)
    )
    events_today = result.scalar() or 0

    return SecurityStatsResponse(
        active_blocks=active_blocks,
        total_blocks=total_blocks,
        failed_attempts_24h=failed_attempts_24h,
        blocked_today=blocked_today,
        events_today=events_today
    )


@router.get("/blocked", response_model=BlockedIPListResponse)
async def get_blocked_ips(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get list of blocked IPs"""
    security = SecurityService(db)

    offset = (page - 1) * per_page
    blocked = await security.get_blocked_ips(
        active_only=active_only,
        limit=per_page,
        offset=offset
    )
    total = await security.get_blocked_ip_count(active_only=active_only)

    return BlockedIPListResponse(
        items=[BlockedIPResponse.model_validate(b) for b in blocked],
        total=total,
        page=page,
        per_page=per_page
    )


@router.post("/blocked", response_model=BlockedIPResponse)
async def block_ip_manually(
    data: BlockedIPCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Manually block an IP address"""
    security = SecurityService(db)

    blocked = await security.block_ip_manually(
        ip_address=data.ip_address,
        admin_username=current_admin.username,
        reason=data.reason,
        is_permanent=data.is_permanent,
        duration_minutes=data.duration_minutes
    )

    return BlockedIPResponse.model_validate(blocked)


@router.post("/blocked/{ip_address}/unblock", response_model=BlockedIPResponse)
async def unblock_ip(
    ip_address: str,
    data: UnblockIPRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Unblock an IP address"""
    security = SecurityService(db)

    success = await security.unblock_ip(
        ip_address=ip_address,
        admin_username=current_admin.username,
        notes=data.notes
    )

    if not success:
        raise HTTPException(status_code=404, detail="IP not found or not blocked")

    # Get updated block record
    result = await db.execute(
        select(BlockedIP).where(BlockedIP.ip_address == ip_address).order_by(BlockedIP.id.desc())
    )
    block = result.scalar_one_or_none()

    return BlockedIPResponse.model_validate(block)


@router.get("/blocked/{ip_address}", response_model=BlockedIPResponse)
async def get_blocked_ip_details(
    ip_address: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get details for a specific blocked IP"""
    result = await db.execute(
        select(BlockedIP).where(BlockedIP.ip_address == ip_address).order_by(BlockedIP.id.desc())
    )
    block = result.scalar_one_or_none()

    if not block:
        raise HTTPException(status_code=404, detail="IP not found")

    return BlockedIPResponse.model_validate(block)


@router.get("/failed-attempts", response_model=list[FailedLoginResponse])
async def get_failed_attempts(
    ip_address: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get recent failed login attempts"""
    security = SecurityService(db)
    attempts = await security.get_recent_failed_attempts(
        ip_address=ip_address,
        limit=limit
    )
    return [FailedLoginResponse.model_validate(a) for a in attempts]


@router.get("/events", response_model=list[SecurityEventResponse])
async def get_security_events(
    event_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get security events log"""
    security = SecurityService(db)
    events = await security.get_security_events(
        event_type=event_type,
        limit=limit
    )
    return [SecurityEventResponse.model_validate(e) for e in events]


@router.post("/cleanup")
async def cleanup_old_records(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Clean up old security records"""
    security = SecurityService(db)
    await security.cleanup_old_records(days=days)
    return {"message": f"Cleaned up records older than {days} days"}
