from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.client import Client


class WireguardConfig(Base):
    """WireGuard configuration for a client"""
    __tablename__ = "wireguard_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), unique=True)

    # WireGuard keys
    private_key: Mapped[str] = mapped_column(String(64))
    public_key: Mapped[str] = mapped_column(String(64))

    # Preshared key for additional security (optional)
    preshared_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Assigned IP address in the WireGuard network
    assigned_ip: Mapped[str] = mapped_column(String(20))  # e.g., "10.10.0.2"

    # Traffic stats
    traffic_up: Mapped[int] = mapped_column(default=0)
    traffic_down: Mapped[int] = mapped_column(default=0)
    last_handshake: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    client: Mapped["Client"] = relationship(back_populates="wireguard_config")


class WireguardServerConfig(Base):
    """Global WireGuard server configuration (singleton)"""
    __tablename__ = "wireguard_server_config"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Server keys
    private_key: Mapped[str] = mapped_column(String(64))
    public_key: Mapped[str] = mapped_column(String(64))

    # Network settings
    interface: Mapped[str] = mapped_column(String(20), default="wg0")
    listen_port: Mapped[int] = mapped_column(default=51820)
    server_ip: Mapped[str] = mapped_column(String(20), default="10.10.0.1")
    subnet: Mapped[str] = mapped_column(String(20), default="10.10.0.0/24")

    # DNS for clients
    dns: Mapped[str] = mapped_column(String(100), default="1.1.1.1,8.8.8.8")

    # MTU (important for performance)
    mtu: Mapped[int] = mapped_column(default=1420)

    # wstunnel settings for obfuscation (optional)
    wstunnel_enabled: Mapped[bool] = mapped_column(default=False)
    wstunnel_port: Mapped[int] = mapped_column(default=443)
    wstunnel_path: Mapped[str] = mapped_column(String(100), default="/ws")

    is_enabled: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, onupdate=datetime.utcnow)
