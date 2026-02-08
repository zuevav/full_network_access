from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.client import Client


class ClientDomain(Base):
    __tablename__ = "client_domains"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    domain: Mapped[str] = mapped_column(String(255))
    include_subdomains: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    added_at: Mapped[datetime] = mapped_column(default=func.now())

    client: Mapped["Client"] = relationship(back_populates="domains")

    __table_args__ = (UniqueConstraint("client_id", "domain"),)


class DomainTemplate(Base):
    __tablename__ = "domain_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    domains_json: Mapped[str] = mapped_column(Text)  # JSON array
    is_active: Mapped[bool] = mapped_column(default=True)
    is_public: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
