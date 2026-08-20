import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.category import Category
from app.models.user import User
from app.schemas.expense import AuditLogResponse, CreateExpenseRequest, EditExpenseRequest, ExpenseResponse
from app.services import expense_service
from app.services.trip_service import get_membership_or_403

router = APIRouter(tags=["expenses"])


@router.post("/trips/{trip_id}/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    trip_id: uuid.UUID,
    payload: CreateExpenseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    expense = await expense_service.create_expense(db, trip_id, current_user.id, payload)
    return ExpenseResponse.model_validate(expense)


@router.get("/trips/{trip_id}/expenses", response_model=list[ExpenseResponse])
async def list_expenses(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ExpenseResponse]:
    await get_membership_or_403(db, trip_id, current_user.id)
    expenses = await expense_service.list_trip_expenses(db, trip_id)
    return [ExpenseResponse.model_validate(e) for e in expenses]


@router.patch("/trips/{trip_id}/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    trip_id: uuid.UUID,
    expense_id: uuid.UUID,
    payload: EditExpenseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    expense = await expense_service.update_expense(db, trip_id, expense_id, current_user.id, payload)
    return ExpenseResponse.model_validate(expense)


@router.delete("/trips/{trip_id}/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    trip_id: uuid.UUID,
    expense_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await expense_service.delete_expense(db, trip_id, expense_id, current_user.id)


@router.get("/trips/{trip_id}/expenses/audit-log", response_model=list[AuditLogResponse])
async def get_expense_audit_log(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogResponse]:
    logs = await expense_service.list_expense_audit_log(db, trip_id, current_user.id)
    return [AuditLogResponse.model_validate(log) for log in logs]


@router.get("/categories", response_model=list[dict])
async def list_categories(db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(select(Category).where(Category.trip_id.is_(None)))
    categories = result.scalars().all()
    return [{"id": str(c.id), "name": c.name, "icon": c.icon} for c in categories]