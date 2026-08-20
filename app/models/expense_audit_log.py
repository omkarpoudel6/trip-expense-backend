"""
ExpenseAuditLog -- an append-only record of who created, edited, or
deleted each expense. Never edited or deleted itself. This exists
specifically so that deleting an expense you owe money on is visible
and attributable, not silent.
"""
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditAction(str, enum.Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class ExpenseAuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expense_audit_logs"

    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), nullable=False)
    expense_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expenses.id"), nullable=False)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    performed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("trip_members.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:
        return f"<ExpenseAuditLog id={self.id} action={self.action} expense_id={self.expense_id}>"