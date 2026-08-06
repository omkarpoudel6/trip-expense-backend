"""
Category model. Global default categories (trip_id=None) plus optional
trip-specific custom categories.
"""
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    trip_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("trips.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name}>"