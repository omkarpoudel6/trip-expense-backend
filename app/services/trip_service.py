"""
Trip management business logic: create, read, edit, archive.
Authorization (admin-only actions) lives here, not in routes -- a route
should never need to know the rules for who's allowed to do what.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trip import Trip, TripStatus
from app.models.trip_member import MemberRole, MemberStatus, TripMember
from app.schemas.trip import CreateTripRequest, UpdateTripRequest


async def get_trip_or_404(db: AsyncSession, trip_id: uuid.UUID) -> Trip:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found.")
    return trip


async def get_membership_or_403(
    db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID
) -> TripMember:
    result = await db.execute(
        select(TripMember).where(
            TripMember.trip_id == trip_id,
            TripMember.user_id == user_id,
            TripMember.status == MemberStatus.ACTIVE,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this trip.",
        )
    return membership


async def require_admin(db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID) -> TripMember:
    membership = await get_membership_or_403(db, trip_id, user_id)
    if membership.role != MemberRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a trip admin can perform this action.",
        )
    return membership


async def create_trip(db: AsyncSession, user_id: uuid.UUID, payload: CreateTripRequest) -> Trip:
    trip = Trip(
        created_by=user_id,
        name=payload.name,
        destination=payload.destination,
        start_date=payload.start_date,
        end_date=payload.end_date,
        base_currency=payload.base_currency,
        budget=payload.budget,
        cover_photo_url=payload.cover_photo_url,
        description=payload.description,
    )
    db.add(trip)
    await db.flush()  # populate trip.id without committing yet

    creator_membership = TripMember(trip_id=trip.id, user_id=user_id, role=MemberRole.ADMIN)
    db.add(creator_membership)

    await db.commit()
    await db.refresh(trip)
    return trip


async def get_trip(db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID) -> Trip:
    await get_membership_or_403(db, trip_id, user_id)
    return await get_trip_or_404(db, trip_id)


async def update_trip(
    db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID, payload: UpdateTripRequest
) -> Trip:
    await require_admin(db, trip_id, user_id)
    trip = await get_trip_or_404(db, trip_id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(trip, field, value)

    await db.commit()
    await db.refresh(trip)
    return trip


async def archive_trip(db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID) -> Trip:
    await require_admin(db, trip_id, user_id)
    trip = await get_trip_or_404(db, trip_id)
    trip.status = TripStatus.ARCHIVED
    await db.commit()
    await db.refresh(trip)
    return trip