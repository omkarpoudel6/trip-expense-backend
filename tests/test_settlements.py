"""
Settlement engine tests: balance calculation and debt-minimization,
verified against known scenarios with a hand-checkable correct answer.
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.category import Category
from app.models.trip_member import TripMember
from app.schemas.auth import RegisterRequest
from app.schemas.expense import CreateExpenseRequest
from app.schemas.trip import CreateTripRequest
from app.services import auth_service, expense_service, settlement_service, trip_invite_service, trip_service


async def _build_trip_with_members(db_session, emails: list[str]) -> tuple:
    users = []
    for i, email in enumerate(emails):
        user = await auth_service.register_user(
            db_session, RegisterRequest(email=email, password="TestPass123", display_name=f"User{i}")
        )
        users.append(user)

    trip = await trip_service.create_trip(
        db_session, users[0].id,
        CreateTripRequest(name="Settlement Test", destination="X", start_date="2026-12-01", end_date="2026-12-05", base_currency="USD"),
    )
    invite = await trip_invite_service.create_invite(db_session, trip.id, users[0].id)
    for user in users[1:]:
        await trip_invite_service.join_trip_by_code(db_session, invite.code, user.id)

    members_result = await db_session.execute(select(TripMember).where(TripMember.trip_id == trip.id))
    member_map = {tm.user_id: tm.id for tm in members_result.scalars().all()}

    return trip, users, member_map


@pytest.mark.asyncio
async def test_balances_sum_to_zero(client, db_session):
    trip, users, m = await _build_trip_with_members(db_session, ["s1@example.com", "s2@example.com", "s3@example.com"])
    category = (await db_session.execute(select(Category).where(Category.name == "Food"))).scalars().first()

    await expense_service.create_expense(
        db_session, trip.id, users[0].id,
        CreateExpenseRequest(
            category_id=category.id, paid_by=m[users[0].id], amount=100.00, currency="USD",
            split_type="equal", split_between=[m[users[0].id], m[users[1].id], m[users[2].id]],
            expense_date="2026-12-02", client_uuid=uuid.uuid4(),
        ),
    )

    balances = await settlement_service.calculate_balances(db_session, trip.id)
    assert sum(balances.values()) == Decimal("0.00")


@pytest.mark.asyncio
async def test_minimize_settlements_produces_minimum_transfers(db_session):
    a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    balances = {a: Decimal("50"), b: Decimal("30"), c: Decimal("-40"), d: Decimal("-40")}

    from app.services.settlement_service import minimize_settlements
    transfers = minimize_settlements(balances)

    # Replay transfers and confirm everyone lands at exactly zero
    check = dict(balances)
    for frm, to, amt in transfers:
        check[frm] += amt
        check[to] -= amt
    assert all(v == Decimal("0") for v in check.values())

    # 4 people, no exact sub-matches -- true minimum is n-1 = 3
    assert len(transfers) == 3


@pytest.mark.asyncio
async def test_minimize_settlements_simple_two_person_case():
    from app.services.settlement_service import minimize_settlements

    a, b = uuid.uuid4(), uuid.uuid4()
    balances = {a: Decimal("50.00"), b: Decimal("-50.00")}

    transfers = minimize_settlements(balances)
    assert len(transfers) == 1
    assert transfers[0] == (b, a, Decimal("50.00"))


@pytest.mark.asyncio
async def test_minimize_settlements_ignores_zero_balances():
    from app.services.settlement_service import minimize_settlements

    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    balances = {a: Decimal("30.00"), b: Decimal("0.00"), c: Decimal("-30.00")}

    transfers = minimize_settlements(balances)
    assert len(transfers) == 1
    assert transfers[0] == (c, a, Decimal("30.00"))


@pytest.mark.asyncio
async def test_confirm_settlement_creates_record(client, db_session):
    trip, users, m = await _build_trip_with_members(db_session, ["cs1@example.com", "cs2@example.com"])

    settlement = await settlement_service.confirm_settlement(
        db_session, trip.id, m[users[1].id], m[users[0].id], Decimal("25.00")
    )

    assert settlement.amount == Decimal("25.00")
    assert settlement.status.value == "confirmed"
    assert settlement.from_member == m[users[1].id]
    assert settlement.to_member == m[users[0].id]


@pytest.mark.asyncio
async def test_get_balances_endpoint(client, db_session):
    trip, users, m = await _build_trip_with_members(db_session, ["ge1@example.com", "ge2@example.com"])
    category = (await db_session.execute(select(Category).where(Category.name == "Food"))).scalars().first()

    await expense_service.create_expense(
        db_session, trip.id, users[0].id,
        CreateExpenseRequest(
            category_id=category.id, paid_by=m[users[0].id], amount=60.00, currency="USD",
            split_type="equal", split_between=[m[users[0].id], m[users[1].id]],
            expense_date="2026-12-02", client_uuid=uuid.uuid4(),
        ),
    )

    login_resp = await client.post("/api/v1/auth/login", json={"email": "ge1@example.com", "password": "TestPass123"})
    headers = {"Authorization": f"Bearer {login_resp.json()['tokens']['access_token']}"}

    response = await client.get(f"/api/v1/trips/{trip.id}/balances", headers=headers)
    assert response.status_code == 200
    balances = response.json()
    assert balances[str(m[users[0].id])] == "30.00"
    assert balances[str(m[users[1].id])] == "-30.00"
    
@pytest.mark.asyncio
async def test_settlement_history_returns_confirmed_settlements(db_session):
    from app.schemas.auth import RegisterRequest
    from app.schemas.trip import CreateTripRequest
    from app.services import auth_service, trip_service, trip_invite_service
    from sqlalchemy import select
    from app.models.trip_member import TripMember

    owner = await auth_service.register_user(
        db_session, RegisterRequest(email="hist1@example.com", password="TestPass123", display_name="Owner")
    )
    member = await auth_service.register_user(
        db_session, RegisterRequest(email="hist2@example.com", password="TestPass123", display_name="Member")
    )
    trip = await trip_service.create_trip(
        db_session, owner.id,
        CreateTripRequest(name="History Test", destination="X", start_date="2026-12-01", end_date="2026-12-05", base_currency="USD"),
    )
    invite = await trip_invite_service.create_invite(db_session, trip.id, owner.id)
    await trip_invite_service.join_trip_by_code(db_session, invite.code, member.id)

    members_result = await db_session.execute(select(TripMember).where(TripMember.trip_id == trip.id))
    members = {m.user_id: m.id for m in members_result.scalars().all()}

    await settlement_service.confirm_settlement(db_session, trip.id, members[member.id], members[owner.id], Decimal("30.00"))

    history = await settlement_service.list_confirmed_settlements(db_session, trip.id)
    assert len(history) == 1
    assert history[0].amount == Decimal("30.00")