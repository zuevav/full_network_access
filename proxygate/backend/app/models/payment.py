from datetime import datetime, date
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, func, Float, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.client import Client


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    paid_at: Mapped[datetime] = mapped_column(default=func.now())
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="paid")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="payments")
