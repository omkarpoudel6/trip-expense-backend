"""
Balance and settlement calculation. Balances are always derived from
expenses and splits, never stored -- a stored balance would drift out of
sync the moment any expense is added, edited, or deleted.
"""
import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense, ExpenseSplit
from app.models.trip_member import MemberStatus, TripMember


async def calculate_balances(db: AsyncSession, trip_id: uuid.UUID) -> dict[uuid.UUID, Decimal]:
    """
    Returns {trip_member_id: net_balance}. Positive = this member is owed
    money overall. Negative = this member owes money overall. Only active
    members are included; the sum of all balances is always zero.
    """
    members_result = await db.execute(
        select(TripMember.id).where(
            TripMember.trip_id == trip_id, TripMember.status == MemberStatus.ACTIVE
        )
    )
    member_ids = {row[0] for row in members_result.all()}

    balances: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0.00"))

    expenses_result = await db.execute(
        select(Expense).where(Expense.trip_id == trip_id, Expense.is_deleted.is_(False))
    )
    expenses = expenses_result.scalars().all()

    for expense in expenses:
        if expense.paid_by in member_ids:
            balances[expense.paid_by] += Decimal(str(expense.amount))

        splits_result = await db.execute(
            select(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id)
        )
        for split in splits_result.scalars().all():
            if split.trip_member_id in member_ids:
                balances[split.trip_member_id] -= Decimal(str(split.share_amount))

    # Ensure every active member appears, even with a zero balance.
    for member_id in member_ids:
        balances.setdefault(member_id, Decimal("0.00"))

    return dict(balances)