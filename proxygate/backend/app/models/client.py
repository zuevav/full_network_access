from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.vpn import VpnConfig
    from app.models.proxy import ProxyAccount
    from app.models.domain import ClientDomain
    from app.models.payment import Payment
    from app.models.domain_request import DomainRequest
    from app.models.xray import XrayConfig
    from app.models.wireguard import WireguardConfig
    from app.models.ip_whitelist import IpWhitelistLog


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    telegram_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    service_type: Mapped[str] = mapped_column(String(20), default="both")  # vpn / proxy / both
    is_active: Mapped[bool] = mapped_column(default=True)
    access_token: Mapped[str] = mapped_column(String(64), unique=True)  # Secret token for client page
    portal_password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Hash for portal login
    access_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    vpn_config: Mapped[Optional["VpnConfig"]] = relationship(
        back_populates="client",
        uselist=False,
        cascade="all, delete-orphan"
    )
    proxy_account: Mapped[Optional["ProxyAccount"]] = relationship(
        back_populates="client",
        uselist=False,
        cascade="all, delete-orphan"
    )
    domains: Mapped[List["ClientDomain"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan"
    )
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan"
    )
    domain_requests: Mapped[List["DomainRequest"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan"
    )
    xray_config: Mapped[Optional["XrayConfig"]] = relationship(
        back_populates="client",
        uselist=False,
        cascade="all, delete-orphan"
    )
    wireguard_config: Mapped[Optional["WireguardConfig"]] = relationship(
        back_populates="client",
        uselist=False,
        cascade="all, delete-orphan"
    )
    ip_whitelist_logs: Mapped[List["IpWhitelistLog"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan"
    )
