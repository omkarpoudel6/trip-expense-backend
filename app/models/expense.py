"""
Expense and ExpenseSplit models -- the financial core of the app.

Critical invariant, enforced at the service layer (not just here):
sum(expense_split.share_amount for one expense) == expense.amount, exactly.
Any leftover cent from an equal split goes to the payer. Never trust
float arithmetic for money -- always Numeric.
"""
import enum
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SplitType(str, enum.Enum):
    EQUAL = "equal"
    EXACT = "exact"


class Expense(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expenses"

    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), nullable=False)
    paid_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("trip_members.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    split_type: Mapped[SplitType] = mapped_column(
        Enum(SplitType, name="split_type_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    client_uuid: Mapped[uuid.UUID] = mapped_column(unique=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<Expense id={self.id} amount={self.amount} trip_id={self.trip_id}>"


class ExpenseSplit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expense_splits"

    expense_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expenses.id"), nullable=False)
    trip_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trip_members.id"), nullable=False)
    share_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    def __repr__(self) -> str:
        return f"<ExpenseSplit expense_id={self.expense_id} member={self.trip_member_id} amount={self.share_amount}>"