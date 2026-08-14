"""
TripMember model -- the join table between users and trips, also the
place a "shadow member" (someone without an app account) can live.
"""
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MemberRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"


class MemberStatus(str, enum.Enum):
    ACTIVE = "active"
    REMOVED = "removed"


class TripMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trip_members"

    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole, name="member_role_enum", values_callable=lambda e: [m.value for m in e]),
        default=MemberRole.MEMBER,
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus, name="member_status_enum", values_callable=lambda e: [m.value for m in e]),
        default=MemberStatus.ACTIVE,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<TripMember id={self.id} trip_id={self.trip_id} user_id={self.user_id}>"