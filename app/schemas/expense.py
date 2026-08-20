"""
Request/response schemas for expenses.

CreateExpenseRequest deliberately does NOT accept pre-computed splits for
"equal" -- the server always computes equal splits itself, since trusting
a client-submitted split undermines the whole point of server-side rounding
safety. For "exact" splits, the client specifies amounts, but the server
still validates they sum to the total exactly.
"""
import uuid
from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models.expense import SplitType


class ExactSplitEntry(BaseModel):
    trip_member_id: uuid.UUID
    share_amount: float = Field(gt=0)


class CreateExpenseRequest(BaseModel):
    category_id: uuid.UUID
    paid_by: uuid.UUID  # trip_member_id of whoever paid
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    split_type: SplitType
    split_between: list[uuid.UUID] | None = None  # trip_member_ids, for "equal"
    exact_splits: list[ExactSplitEntry] | None = None  # for "exact"
    notes: str | None = None
    expense_date: date
    client_uuid: uuid.UUID

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper()


class ExpenseSplitResponse(BaseModel):
    trip_member_id: uuid.UUID
    share_amount: float

    model_config = {"from_attributes": True}


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    trip_id: uuid.UUID
    category_id: uuid.UUID
    paid_by: uuid.UUID
    amount: float
    currency: str
    split_type: SplitType
    notes: str | None
    receipt_url: str | None
    expense_date: date
    splits: list[ExpenseSplitResponse]

    model_config = {"from_attributes": True}
    
    
class EditExpenseRequest(BaseModel):
    category_id: uuid.UUID
    paid_by: uuid.UUID
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    split_type: SplitType
    split_between: list[uuid.UUID] | None = None
    exact_splits: list[ExactSplitEntry] | None = None
    notes: str | None = None
    expense_date: date

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper()


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    expense_id: uuid.UUID
    action: str
    performed_by_name: str
    amount: float
    summary: str
    created_at: str