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
from app.models.settlement import Settlement, SettlementStatus


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

    settlements_result = await db.execute(
        select(Settlement).where(Settlement.trip_id == trip_id, Settlement.status == SettlementStatus.CONFIRMED)
    )
    for settlement in settlements_result.scalars().all():
        # A confirmed settlement is a real payment: the payer's debt shrinks
        # (balance moves toward zero), the receiver's credit shrinks by the
        # same amount -- exactly like the transfer it represents.
        if settlement.from_member in member_ids:
            balances[settlement.from_member] += Decimal(str(settlement.amount))
        if settlement.to_member in member_ids:
            balances[settlement.to_member] -= Decimal(str(settlement.amount))
    
    # Ensure every active member appears, even with a zero balance.
    for member_id in member_ids:
        balances.setdefault(member_id, Decimal("0.00"))

    return dict(balances)

def minimize_settlements(balances: dict[uuid.UUID, Decimal]) -> list[tuple[uuid.UUID, uuid.UUID, Decimal]]:
    """
    Given {trip_member_id: net_balance}, returns a list of
    (from_member_id, to_member_id, amount) transfers that settles
    everyone to zero, using the minimum number of transactions.
    """
    creditors = []
    debtors = []
    for member_id, balance in balances.items():
        if balance > 0:
            creditors.append([member_id, balance])
        elif balance < 0:
            debtors.append([member_id, balance])

    creditors.sort(key=lambda c: c[1], reverse=True)  # largest owed first
    debtors.sort(key=lambda d: d[1])                   # most negative first

    transactions: list[tuple[uuid.UUID, uuid.UUID, Decimal]] = []

    while creditors and debtors:
        creditor = creditors[0]
        debtor = debtors[0]

        transfer_amount = min(creditor[1], -debtor[1])

        transactions.append((debtor[0], creditor[0], transfer_amount))

        creditor[1] -= transfer_amount
        debtor[1] += transfer_amount

        if creditor[1] == 0:
            creditors.pop(0)
        if debtor[1] == 0:
            debtors.pop(0)

    return transactions

async def get_suggested_transfers(db: AsyncSession, trip_id: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID, Decimal]]:
    balances = await calculate_balances(db, trip_id)
    return minimize_settlements(balances)


async def confirm_settlement(
    db: AsyncSession, trip_id: uuid.UUID, from_member: uuid.UUID, to_member: uuid.UUID, amount: Decimal
) -> Settlement:
    settlement = Settlement(
        trip_id=trip_id, from_member=from_member, to_member=to_member,
        amount=amount, status=SettlementStatus.CONFIRMED,
    )
    db.add(settlement)
    await db.commit()
    await db.refresh(settlement)
    
    to_member_row = (await db.execute(select(TripMember).where(TripMember.id == to_member))).scalar_one_or_none()
    if to_member_row and to_member_row.user_id:
        from app.services.notification_service import send_push_to_users
        await send_push_to_users(db, [to_member_row.user_id], "Payment received", f"₹{amount} marked as paid", {"tripId": str(trip_id)})
    
    return settlement

async def list_confirmed_settlements(db: AsyncSession, trip_id: uuid.UUID) -> list[Settlement]:
    result = await db.execute(
        select(Settlement).where(Settlement.trip_id == trip_id).order_by(Settlement.settled_at.desc())
    )
    return list(result.scalars().all())