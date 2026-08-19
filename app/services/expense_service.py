"""
Expense creation logic. This is the most consequential file in the app --
every split calculation flows through here, and the sum-must-equal-total
invariant is enforced before anything touches the database.
"""
import uuid
from decimal import ROUND_DOWN, Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.expense import Expense, ExpenseSplit, SplitType
from app.models.trip_member import MemberStatus, TripMember
from app.schemas.expense import CreateExpenseRequest
from app.services.trip_service import get_membership_or_403


def calculate_equal_splits(total: Decimal, member_ids: list[uuid.UUID], payer_id: uuid.UUID) -> dict[uuid.UUID, Decimal]:
    """
    Split `total` evenly across member_ids. Any leftover cents from integer
    division go to the payer, so the sum always equals `total` exactly --
    never trust float division for money.

    If the payer isn't part of the split (they fronted the cost but didn't
    participate themselves), there's no natural owner for the leftover
    cent(s), so it goes to the first participant instead -- deterministic,
    not a crash.
    """
    count = len(member_ids)
    cents_total = int((total * 100).to_integral_value())
    base_cents = cents_total // count
    remainder_cents = cents_total - (base_cents * count)

    splits = {member_id: Decimal(base_cents) / 100 for member_id in member_ids}

    remainder_recipient = payer_id if payer_id in splits else member_ids[0]
    splits[remainder_recipient] += Decimal(remainder_cents) / 100

    return splits


async def create_expense(
    db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID, payload: CreateExpenseRequest
) -> Expense:
    await get_membership_or_403(db, trip_id, user_id)

    # Confirm the payer is a real, active member of this trip.
    payer_check = await db.execute(
        select(TripMember).where(
            TripMember.id == payload.paid_by,
            TripMember.trip_id == trip_id,
            TripMember.status == MemberStatus.ACTIVE,
        )
    )
    if payer_check.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="paid_by is not an active member of this trip."
        )

    amount = Decimal(str(payload.amount)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    split_amounts: dict[uuid.UUID, Decimal]

    if payload.split_type == SplitType.EQUAL:
        if not payload.split_between:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="split_between is required for an equal split.",
            )
        split_amounts = calculate_equal_splits(amount, payload.split_between, payload.paid_by)

    elif payload.split_type == SplitType.EXACT:
        if not payload.exact_splits:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="exact_splits is required for an exact split.",
            )
        split_amounts = {
            entry.trip_member_id: Decimal(str(entry.share_amount)).quantize(Decimal("0.01"))
            for entry in payload.exact_splits
        }
        total_of_splits = sum(split_amounts.values())
        if total_of_splits != amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"exact_splits sum to {total_of_splits}, but amount is {amount}.",
            )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported split_type.")

    # Final safety check -- this must always be true regardless of which
    # branch above ran. If it's ever false, something upstream is broken.
    assert sum(split_amounts.values()) == amount, "Split sum does not match expense amount"

    expense = Expense(
        trip_id=trip_id,
        category_id=payload.category_id,
        paid_by=payload.paid_by,
        amount=amount,
        currency=payload.currency,
        split_type=payload.split_type,
        notes=payload.notes,
        expense_date=payload.expense_date,
        client_uuid=payload.client_uuid,
    )
    db.add(expense)
    await db.flush()

    for member_id, share in split_amounts.items():
        db.add(ExpenseSplit(expense_id=expense.id, trip_member_id=member_id, share_amount=share))

    await db.commit()
    #await db.refresh(expense)
    await db.refresh(expense, attribute_names=["splits"])
    return expense

async def list_trip_expenses(db: AsyncSession, trip_id: uuid.UUID) -> list[Expense]:
    result = await db.execute(
        select(Expense)
        .options(selectinload(Expense.splits))
        .where(Expense.trip_id == trip_id, Expense.is_deleted.is_(False))
        .order_by(Expense.created_at.desc())
    )
    return list(result.scalars().all())