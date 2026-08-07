"""
Settlement model -- a record that a specific payment was made between two
trip members. Record-only (no real payment processing). Balances remain
derived from expenses; this table is just a paper trail of settlements.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SettlementStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class Settlement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "settlements"

    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), nullable=False)
    from_member: Mapped[uuid.UUID] = mapped_column(ForeignKey("trip_members.id"), nullable=False)
    to_member: Mapped[uuid.UUID] = mapped_column(ForeignKey("trip_members.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[SettlementStatus] = mapped_column(
        Enum(SettlementStatus, name="settlement_status_enum", values_callable=lambda e: [m.value for m in e]),
        default=SettlementStatus.CONFIRMED,
        nullable=False,
    )
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Settlement id={self.id} from={self.from_member} to={self.to_member} amount={self.amount}>"