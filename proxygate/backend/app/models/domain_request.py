from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.client import Client


class DomainRequest(Base):
    __tablename__ = "domain_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    domain: Mapped[str] = mapped_column(String(255))  # Requested domain
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Why needed (from client)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / approved / rejected
    admin_comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Admin comment
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    client: Mapped["Client"] = relationship(back_populates="domain_requests")
