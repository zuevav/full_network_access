from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.client import Client


class IpWhitelistLog(Base):
    __tablename__ = "ip_whitelist_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    ip_address: Mapped[str] = mapped_column(String(45))
    action: Mapped[str] = mapped_column(String(10))  # "added" / "removed"
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    client: Mapped["Client"] = relationship(back_populates="ip_whitelist_logs")
