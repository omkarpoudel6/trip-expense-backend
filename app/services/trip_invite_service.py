"""
Invite generation and join-by-code logic.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trip import Trip
from app.models.trip_invite import Invite
from app.models.trip_member import MemberRole, MemberStatus, TripMember
from app.services.trip_service import get_trip_or_404, require_admin


async def create_invite(db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID) -> Invite:
    await require_admin(db, trip_id, user_id)
    await get_trip_or_404(db, trip_id)

    invite = Invite(trip_id=trip_id, created_by=user_id)
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


async def join_trip_by_code(db: AsyncSession, code: str, user_id: uuid.UUID) -> Trip:
    result = await db.execute(select(Invite).where(Invite.code == code))
    invite = result.scalar_one_or_none()

    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite code.")

    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This invite has expired.")

    trip = await get_trip_or_404(db, invite.trip_id)

    existing = await db.execute(
        select(TripMember).where(
            TripMember.trip_id == trip.id,
            TripMember.user_id == user_id,
        )
    )
    membership = existing.scalar_one_or_none()

    if membership is not None and membership.status == MemberStatus.ACTIVE:
        # Already a member -- not an error, just return the trip (per UI/UX spec).
        return trip

    if membership is not None and membership.status == MemberStatus.REMOVED:
        # Rejoining after being removed: reactivate rather than duplicate.
        membership.status = MemberStatus.ACTIVE
    else:
        membership = TripMember(trip_id=trip.id, user_id=user_id, role=MemberRole.MEMBER)
        db.add(membership)

    await db.commit()
    return trip