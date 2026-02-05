from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.client import Client


class XrayConfig(Base):
    """XRay VLESS + REALITY configuration for a client"""
    __tablename__ = "xray_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), unique=True)

    # VLESS UUID for this client
    uuid: Mapped[str] = mapped_column(String(36), unique=True)

    # Optional: custom short_id for this client (if different from global)
    short_id: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Traffic stats (updated periodically)
    traffic_up: Mapped[int] = mapped_column(default=0)  # bytes uploaded
    traffic_down: Mapped[int] = mapped_column(default=0)  # bytes downloaded

    # Expiration (optional, for time-limited access)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    client: Mapped["Client"] = relationship(back_populates="xray_config")


class XrayServerConfig(Base):
    """Global XRay server configuration (singleton)"""
    __tablename__ = "xray_server_config"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Server settings
    port: Mapped[int] = mapped_column(default=443)

    # REALITY settings
    private_key: Mapped[str] = mapped_column(String(64))
    public_key: Mapped[str] = mapped_column(String(64))
    short_id: Mapped[str] = mapped_column(String(16))

    # Destination for REALITY (masquerade target)
    dest_server: Mapped[str] = mapped_column(String(255), default="www.microsoft.com")
    dest_port: Mapped[int] = mapped_column(default=443)
    server_name: Mapped[str] = mapped_column(String(255), default="www.microsoft.com")

    # Is XRay enabled on this server?
    is_enabled: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, onupdate=datetime.utcnow)
