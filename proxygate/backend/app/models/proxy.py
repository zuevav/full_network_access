from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, ForeignKey, Text, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship, deferred

from app.database import Base

if TYPE_CHECKING:
    from app.models.client import Client


class ProxyAccount(Base):
    __tablename__ = "proxy_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), unique=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    password_plain: Mapped[str] = mapped_column(String(64))  # For admin display
    is_active: Mapped[bool] = mapped_column(default=True)
    # IP addresses that can access proxy without authentication (comma-separated)
    # Using deferred() to prevent errors if column doesn't exist yet (before migration)
    allowed_ips = deferred(Column(Text, nullable=True))

    client: Mapped["Client"] = relationship(back_populates="proxy_account")
