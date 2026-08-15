import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.settlement import ConfirmSettlementRequest, SettlementResponse, SuggestedTransfer
from app.services import settlement_service
from app.services.trip_service import get_membership_or_403

router = APIRouter(prefix="/trips/{trip_id}", tags=["settlements"])


@router.get("/balances")
async def get_balances(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await get_membership_or_403(db, trip_id, current_user.id)
    balances = await settlement_service.calculate_balances(db, trip_id)
    return {str(member_id): str(balance) for member_id, balance in balances.items()}


@router.get("/settlements", response_model=list[SuggestedTransfer])
async def get_suggested_settlements(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SuggestedTransfer]:
    await get_membership_or_403(db, trip_id, current_user.id)
    transfers = await settlement_service.get_suggested_transfers(db, trip_id)
    return [SuggestedTransfer(from_member=f, to_member=t, amount=a) for f, t, a in transfers]


@router.post("/settlements/confirm", response_model=SettlementResponse)
async def confirm_settlement(
    trip_id: uuid.UUID,
    payload: ConfirmSettlementRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SettlementResponse:
    await get_membership_or_403(db, trip_id, current_user.id)
    settlement = await settlement_service.confirm_settlement(
        db, trip_id, payload.from_member, payload.to_member, payload.amount
    )
    return SettlementResponse(
        id=settlement.id, trip_id=settlement.trip_id, from_member=settlement.from_member,
        to_member=settlement.to_member, amount=settlement.amount,
        status=settlement.status.value, settled_at=settlement.settled_at.isoformat(),
    )
    
@router.get("/settlements/history", response_model=list[SettlementResponse])
async def get_settlement_history(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SettlementResponse]:
    await get_membership_or_403(db, trip_id, current_user.id)
    settlements = await settlement_service.list_confirmed_settlements(db, trip_id)
    return [
        SettlementResponse(
            id=s.id, trip_id=s.trip_id, from_member=s.from_member, to_member=s.to_member,
            amount=s.amount, status=s.status.value, settled_at=s.settled_at.isoformat(),
        )
        for s in settlements
    ]