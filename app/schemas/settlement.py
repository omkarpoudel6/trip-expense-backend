import uuid
from decimal import Decimal

from pydantic import BaseModel


class BalanceEntry(BaseModel):
    trip_member_id: uuid.UUID
    net_balance: Decimal


class SuggestedTransfer(BaseModel):
    from_member: uuid.UUID
    to_member: uuid.UUID
    amount: Decimal


class ConfirmSettlementRequest(BaseModel):
    from_member: uuid.UUID
    to_member: uuid.UUID
    amount: Decimal


class SettlementResponse(BaseModel):
    id: uuid.UUID
    trip_id: uuid.UUID
    from_member: uuid.UUID
    to_member: uuid.UUID
    amount: Decimal
    status: str
    settled_at: str

    model_config = {"from_attributes": True}