"""
Security models for brute force protection
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from app.database import Base


class FailedLogin(Base):
    """Track failed login attempts"""
    __tablename__ = "failed_logins"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), index=True)  # IPv4 or IPv6
    username = Column(String(255), nullable=True)  # attempted username
    user_agent = Column(Text, nullable=True)
    endpoint = Column(String(100))  # /api/auth/login, /api/portal/auth, etc.
    attempt_time = Column(DateTime, default=datetime.utcnow)


class BlockedIP(Base):
    """Blocked IPs after too many failed attempts"""
    __tablename__ = "blocked_ips"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), unique=True, index=True)
    reason = Column(String(255))  # "Too many failed login attempts"
    failed_attempts = Column(Integer, default=0)
    blocked_at = Column(DateTime, default=datetime.utcnow)
    blocked_until = Column(DateTime, nullable=True)  # null = permanent
    is_permanent = Column(Boolean, default=False)
    unblocked_at = Column(DateTime, nullable=True)
    unblocked_by = Column(String(100), nullable=True)  # admin username
    is_active = Column(Boolean, default=True)  # false = unblocked
    notes = Column(Text, nullable=True)


class SecurityEvent(Base):
    """Security audit log"""
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), index=True)  # login_failed, ip_blocked, ip_unblocked, etc.
    ip_address = Column(String(45), nullable=True)
    username = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
