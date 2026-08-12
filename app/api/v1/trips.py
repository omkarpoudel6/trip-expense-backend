import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.trip import (
    CreateTripRequest,
    InviteResponse,
    JoinTripRequest,
    TripResponse,
    UpdateTripRequest,
)
from app.services import trip_invite_service, trip_service

router = APIRouter(prefix="/trips", tags=["trips"])

@router.get("", response_model=list[TripResponse])
async def list_trips(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TripResponse]:
    trips = await trip_service.list_user_trips(db, current_user.id)
    return [TripResponse.model_validate(t) for t in trips]


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
async def create_trip(
    payload: CreateTripRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TripResponse:
    trip = await trip_service.create_trip(db, current_user.id, payload)
    return TripResponse.model_validate(trip)


@router.get("/{trip_id}", response_model=TripResponse)
async def get_trip(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TripResponse:
    trip = await trip_service.get_trip(db, trip_id, current_user.id)
    return TripResponse.model_validate(trip)


@router.patch("/{trip_id}", response_model=TripResponse)
async def update_trip(
    trip_id: uuid.UUID,
    payload: UpdateTripRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TripResponse:
    trip = await trip_service.update_trip(db, trip_id, current_user.id, payload)
    return TripResponse.model_validate(trip)


@router.post("/{trip_id}/archive", response_model=TripResponse)
async def archive_trip(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TripResponse:
    trip = await trip_service.archive_trip(db, trip_id, current_user.id)
    return TripResponse.model_validate(trip)


@router.post("/{trip_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_trip(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await trip_service.leave_trip(db, trip_id, current_user.id)


@router.delete("/{trip_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    trip_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await trip_service.remove_member(db, trip_id, current_user.id, member_id)


@router.post("/{trip_id}/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InviteResponse:
    invite = await trip_invite_service.create_invite(db, trip_id, current_user.id)
    return InviteResponse(
        code=invite.code, link_token=invite.link_token, expires_at=invite.expires_at.isoformat()
    )


@router.post("/join", response_model=TripResponse)
async def join_trip(
    payload: JoinTripRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TripResponse:
    trip = await trip_invite_service.join_trip_by_code(db, payload.code, current_user.id)
    return TripResponse.model_validate(trip)