from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.client import Client


class VpnConfig(Base):
    __tablename__ = "vpn_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), unique=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)  # EAP username: client_001
    password: Mapped[str] = mapped_column(String(64))  # EAP password (plaintext for strongSwan)
    assigned_ip: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Fixed IP from pool (optional)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Cache of resolved IPs for routes
    resolved_routes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of CIDRs
    last_resolved: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    client: Mapped["Client"] = relationship(back_populates="vpn_config")
