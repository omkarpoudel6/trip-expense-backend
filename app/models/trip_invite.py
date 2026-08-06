"""
Invite model -- a join code or link, tied to one trip.
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

INVITE_EXPIRY_DAYS = 7


def generate_invite_code() -> str:
    """8-character, human-typeable code (uppercase letters + digits)."""
    return secrets.token_hex(4).upper()


def default_invite_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRY_DAYS)


class Invite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invites"

    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False, default=generate_invite_code)
    link_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32)
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=default_invite_expiry
    )

    def __repr__(self) -> str:
        return f"<Invite id={self.id} trip_id={self.trip_id} code={self.code}>"