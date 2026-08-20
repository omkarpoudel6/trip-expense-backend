"""
Expense creation, editing, and deletion logic. This is the most
consequential file in the app -- every split calculation flows through
here, and the sum-must-equal-total invariant is enforced before anything
touches the database. Every create/update/delete also writes an
append-only audit log entry, since silently losing a transaction someone
owes money on is exactly the kind of thing that must be attributable.
"""
import uuid
from decimal import ROUND_DOWN, Decimal

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.expense import Expense, ExpenseSplit, SplitType
from app.models.expense_audit_log import AuditAction, ExpenseAuditLog
from app.models.trip_member import MemberStatus, TripMember
from app.models.user import User
from app.schemas.expense import CreateExpenseRequest, EditExpenseRequest, ExactSplitEntry
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


def _resolve_splits(
    amount: Decimal,
    split_type: SplitType,
    split_between: list[uuid.UUID] | None,
    exact_splits: list[ExactSplitEntry] | None,
    payer_id: uuid.UUID,
) -> dict[uuid.UUID, Decimal]:
    """Shared by create_expense and update_expense so both use identical
    validation and rounding rules -- editing an expense should never be
    held to a looser standard than creating one."""
    if split_type == SplitType.EQUAL:
        if not split_between:
            raise HTTPException(status_code=400, detail="split_between is required for an equal split.")
        return calculate_equal_splits(amount, split_between, payer_id)

    if split_type == SplitType.EXACT:
        if not exact_splits:
            raise HTTPException(status_code=400, detail="exact_splits is required for an exact split.")
        split_amounts = {
            entry.trip_member_id: Decimal(str(entry.share_amount)).quantize(Decimal("0.01"))
            for entry in exact_splits
        }
        total_of_splits = sum(split_amounts.values())
        if total_of_splits != amount:
            raise HTTPException(
                status_code=400, detail=f"exact_splits sum to {total_of_splits}, but amount is {amount}."
            )
        return split_amounts

    raise HTTPException(status_code=400, detail="Unsupported split_type.")


async def _verify_active_payer(db: AsyncSession, trip_id: uuid.UUID, paid_by: uuid.UUID) -> None:
    payer_check = await db.execute(
        select(TripMember).where(
            TripMember.id == paid_by, TripMember.trip_id == trip_id, TripMember.status == MemberStatus.ACTIVE
        )
    )
    if payer_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=400, detail="paid_by is not an active member of this trip.")


async def create_expense(
    db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID, payload: CreateExpenseRequest
) -> Expense:
    membership = await get_membership_or_403(db, trip_id, user_id)
    await _verify_active_payer(db, trip_id, payload.paid_by)

    amount = Decimal(str(payload.amount)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    split_amounts = _resolve_splits(amount, payload.split_type, payload.split_between, payload.exact_splits, payload.paid_by)

    # Final safety check -- this must always be true regardless of which
    # branch above ran. If it's ever false, something upstream is broken.
    assert sum(split_amounts.values()) == amount, "Split sum does not match expense amount"

    expense = Expense(
        trip_id=trip_id, category_id=payload.category_id, paid_by=payload.paid_by, amount=amount,
        currency=payload.currency, split_type=payload.split_type, notes=payload.notes,
        expense_date=payload.expense_date, client_uuid=payload.client_uuid,
    )
    db.add(expense)
    await db.flush()

    for member_id, share in split_amounts.items():
        db.add(ExpenseSplit(expense_id=expense.id, trip_member_id=member_id, share_amount=share))

    db.add(ExpenseAuditLog(
        trip_id=trip_id, expense_id=expense.id, action=AuditAction.CREATED, performed_by=membership.id,
        amount=amount, summary=f"Created — {payload.notes or 'expense'} ({amount})",
    ))

    await db.commit()
    await db.refresh(expense, attribute_names=["splits"])
    return expense


async def require_expense_editor(
    db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID, expense: Expense
) -> TripMember:
    """Only the original payer or a trip admin may edit/delete an expense."""
    membership = await get_membership_or_403(db, trip_id, user_id)
    if expense.paid_by == membership.id or membership.role.value == "admin":
        return membership
    raise HTTPException(
        status_code=403, detail="Only the person who paid, or a trip admin, can edit or delete this expense."
    )


async def update_expense(
    db: AsyncSession, trip_id: uuid.UUID, expense_id: uuid.UUID, user_id: uuid.UUID, payload: EditExpenseRequest
) -> Expense:
    result = await db.execute(select(Expense).where(Expense.id == expense_id, Expense.trip_id == trip_id))
    expense = result.scalar_one_or_none()
    if expense is None or expense.is_deleted:
        raise HTTPException(status_code=404, detail="Expense not found.")

    membership = await require_expense_editor(db, trip_id, user_id, expense)
    await _verify_active_payer(db, trip_id, payload.paid_by)

    amount = Decimal(str(payload.amount)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    split_amounts = _resolve_splits(amount, payload.split_type, payload.split_between, payload.exact_splits, payload.paid_by)
    assert sum(split_amounts.values()) == amount, "Split sum does not match expense amount"

    await db.execute(delete(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id))

    expense.category_id = payload.category_id
    expense.paid_by = payload.paid_by
    expense.amount = amount
    expense.currency = payload.currency
    expense.split_type = payload.split_type
    expense.notes = payload.notes
    expense.expense_date = payload.expense_date

    for member_id, share in split_amounts.items():
        db.add(ExpenseSplit(expense_id=expense.id, trip_member_id=member_id, share_amount=share))

    db.add(ExpenseAuditLog(
        trip_id=trip_id, expense_id=expense.id, action=AuditAction.UPDATED, performed_by=membership.id,
        amount=amount, summary=f"Updated — {payload.notes or 'expense'} ({amount})",
    ))

    await db.commit()
    await db.refresh(expense, attribute_names=["splits"])
    return expense


async def delete_expense(db: AsyncSession, trip_id: uuid.UUID, expense_id: uuid.UUID, user_id: uuid.UUID) -> None:
    result = await db.execute(select(Expense).where(Expense.id == expense_id, Expense.trip_id == trip_id))
    expense = result.scalar_one_or_none()
    if expense is None or expense.is_deleted:
        raise HTTPException(status_code=404, detail="Expense not found.")

    membership = await require_expense_editor(db, trip_id, user_id, expense)

    db.add(ExpenseAuditLog(
        trip_id=trip_id, expense_id=expense.id, action=AuditAction.DELETED, performed_by=membership.id,
        amount=expense.amount, summary=f"Deleted — {expense.notes or 'expense'} ({expense.amount})",
    ))

    expense.is_deleted = True
    await db.commit()


async def list_trip_expenses(db: AsyncSession, trip_id: uuid.UUID) -> list[Expense]:
    result = await db.execute(
        select(Expense)
        .options(selectinload(Expense.splits))
        .where(Expense.trip_id == trip_id, Expense.is_deleted.is_(False))
        .order_by(Expense.created_at.desc())
    )
    return list(result.scalars().all())


async def list_expense_audit_log(db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID) -> list[dict]:
    await get_membership_or_403(db, trip_id, user_id)

    result = await db.execute(
        select(ExpenseAuditLog).where(ExpenseAuditLog.trip_id == trip_id).order_by(ExpenseAuditLog.created_at.desc())
    )
    logs = list(result.scalars().all())

    member_ids = {log.performed_by for log in logs}
    members: dict[uuid.UUID, TripMember] = {}
    if member_ids:
        members_result = await db.execute(select(TripMember).where(TripMember.id.in_(member_ids)))
        members = {m.id: m for m in members_result.scalars().all()}

    real_user_ids = [m.user_id for m in members.values() if m.user_id is not None]
    users_by_id: dict[uuid.UUID, User] = {}
    if real_user_ids:
        users_result = await db.execute(select(User).where(User.id.in_(real_user_ids)))
        users_by_id = {u.id: u for u in users_result.scalars().all()}

    response = []
    for log in logs:
        member = members.get(log.performed_by)
        if member and member.user_id and member.user_id in users_by_id:
            performer_name = users_by_id[member.user_id].display_name
        elif member:
            performer_name = member.display_name or "Unnamed member"
        else:
            performer_name = "Unknown"
        response.append({
            "id": log.id, "expense_id": log.expense_id, "action": log.action.value,
            "performed_by_name": performer_name, "amount": log.amount, "summary": log.summary,
            "created_at": log.created_at.isoformat(),
        })
    return response