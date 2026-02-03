from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    client: Mapped["Client"] = relationship(back_populates="proxy_account")
