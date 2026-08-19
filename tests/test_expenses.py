"""
Expense engine tests: equal splits (including the rounding edge case),
exact splits (including sum-mismatch rejection), and invalid-payer checks.
"""
import pytest
from httpx import AsyncClient
from decimal import Decimal


async def _register_and_login(client: AsyncClient, email: str, name: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPass123", "display_name": name},
    )
    return response.json()


def _auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _create_trip_with_members(client: AsyncClient, owner_email: str, member_emails: list[str]):
    """Returns (trip_id, owner_trip_member_id, [other_trip_member_ids], headers_by_email)."""
    owner = await _register_and_login(client, owner_email, "Owner")
    headers = {owner_email: _auth_headers(owner["tokens"])}

    trip_resp = await client.post(
        "/api/v1/trips",
        json={
            "name": "Test Trip", "destination": "Somewhere",
            "start_date": "2026-10-01", "end_date": "2026-10-10", "base_currency": "USD",
        },
        headers=headers[owner_email],
    )
    trip_id = trip_resp.json()["id"]

    invite_resp = await client.post(f"/api/v1/trips/{trip_id}/invites", headers=headers[owner_email])
    code = invite_resp.json()["code"]

    other_member_ids = []
    for email in member_emails:
        user = await _register_and_login(client, email, email.split("@")[0])
        headers[email] = _auth_headers(user["tokens"])
        await client.post("/api/v1/trips/join", json={"code": code}, headers=headers[email])

    # Fetch trip_member ids via the categories/expenses list isn't available yet for members,
    # so pull member ids from a direct DB-free approach: get_trip doesn't expose members list
    # in this milestone's schema, so we derive via listing expenses is not needed here --
    # instead we grab member ids from the join responses is unavailable too.
    # Simplest reliable path: re-use trip_service through db_session directly in the test.
    return trip_id, headers


@pytest.mark.asyncio
async def test_get_categories(client: AsyncClient):
    response = await client.get("/api/v1/categories")
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert "Food" in names
    assert len(response.json()) == 10


@pytest.mark.asyncio
async def test_create_expense_equal_split_with_rounding(client: AsyncClient, db_session):
    from app.schemas.auth import RegisterRequest
    from app.schemas.trip import CreateTripRequest
    from app.services import auth_service, trip_service, trip_invite_service
    from sqlalchemy import select
    from app.models.trip_member import TripMember
    from app.models.category import Category

    owner = await auth_service.register_user(
        db_session, RegisterRequest(email="split1@example.com", password="TestPass123", display_name="Owner")
    )
    m2 = await auth_service.register_user(
        db_session, RegisterRequest(email="split2@example.com", password="TestPass123", display_name="M2")
    )
    m3 = await auth_service.register_user(
        db_session, RegisterRequest(email="split3@example.com", password="TestPass123", display_name="M3")
    )

    trip = await trip_service.create_trip(
        db_session, owner.id,
        CreateTripRequest(name="Split Test", destination="X", start_date="2026-10-01", end_date="2026-10-05", base_currency="USD"),
    )
    invite = await trip_invite_service.create_invite(db_session, trip.id, owner.id)
    await trip_invite_service.join_trip_by_code(db_session, invite.code, m2.id)
    await trip_invite_service.join_trip_by_code(db_session, invite.code, m3.id)

    members_result = await db_session.execute(select(TripMember).where(TripMember.trip_id == trip.id))
    members = {m.user_id: m.id for m in members_result.scalars().all()}

    category_result = await db_session.execute(select(Category).where(Category.name == "Food"))
    category = category_result.scalars().first()

    from app.schemas.expense import CreateExpenseRequest
    from app.services import expense_service
    import uuid as uuid_module

    payload = CreateExpenseRequest(
        category_id=category.id,
        paid_by=members[owner.id],
        amount=1000.00,
        currency="USD",
        split_type="equal",
        split_between=[members[owner.id], members[m2.id], members[m3.id]],
        expense_date="2026-10-02",
        client_uuid=uuid_module.uuid4(),
    )

    expense = await expense_service.create_expense(db_session, trip.id, owner.id, payload)

    split_amounts = sorted(float(s.share_amount) for s in expense.splits)
    assert split_amounts == [333.33, 333.33, 333.34]
    assert sum(float(s.share_amount) for s in expense.splits) == 1000.00


@pytest.mark.asyncio
async def test_exact_split_mismatch_rejected(client: AsyncClient, db_session):
    from app.schemas.auth import RegisterRequest
    from app.schemas.trip import CreateTripRequest
    from app.services import auth_service, trip_service
    from sqlalchemy import select
    from app.models.trip_member import TripMember
    from app.models.category import Category
    from app.schemas.expense import CreateExpenseRequest, ExactSplitEntry
    from app.services import expense_service
    from fastapi import HTTPException
    import uuid as uuid_module

    owner = await auth_service.register_user(
        db_session, RegisterRequest(email="exact1@example.com", password="TestPass123", display_name="Owner")
    )
    trip = await trip_service.create_trip(
        db_session, owner.id,
        CreateTripRequest(name="Exact Test", destination="X", start_date="2026-10-01", end_date="2026-10-05", base_currency="USD"),
    )
    members_result = await db_session.execute(select(TripMember).where(TripMember.trip_id == trip.id))
    owner_member = members_result.scalars().first()

    category_result = await db_session.execute(select(Category).where(Category.name == "Food"))
    category = category_result.scalars().first()

    payload = CreateExpenseRequest(
        category_id=category.id,
        paid_by=owner_member.id,
        amount=100.00,
        currency="USD",
        split_type="exact",
        exact_splits=[ExactSplitEntry(trip_member_id=owner_member.id, share_amount=50.00)],
        expense_date="2026-10-02",
        client_uuid=uuid_module.uuid4(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await expense_service.create_expense(db_session, trip.id, owner.id, payload)

    assert exc_info.value.status_code == 400
    assert "sum to" in exc_info.value.detail


@pytest.mark.asyncio
async def test_invalid_payer_rejected(client: AsyncClient, db_session):
    from app.schemas.auth import RegisterRequest
    from app.schemas.trip import CreateTripRequest
    from app.services import auth_service, trip_service
    from sqlalchemy import select
    from app.models.category import Category
    from app.schemas.expense import CreateExpenseRequest
    from app.services import expense_service
    from fastapi import HTTPException
    import uuid as uuid_module

    owner = await auth_service.register_user(
        db_session, RegisterRequest(email="badpayer@example.com", password="TestPass123", display_name="Owner")
    )
    trip = await trip_service.create_trip(
        db_session, owner.id,
        CreateTripRequest(name="Bad Payer Test", destination="X", start_date="2026-10-01", end_date="2026-10-05", base_currency="USD"),
    )
    category_result = await db_session.execute(select(Category).where(Category.name == "Food"))
    category = category_result.scalars().first()

    fake_member_id = uuid_module.uuid4()
    payload = CreateExpenseRequest(
        category_id=category.id,
        paid_by=fake_member_id,
        amount=100.00,
        currency="USD",
        split_type="equal",
        split_between=[fake_member_id],
        expense_date="2026-10-02",
        client_uuid=uuid_module.uuid4(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await expense_service.create_expense(db_session, trip.id, owner.id, payload)

    assert exc_info.value.status_code == 400
    assert "not an active member" in exc_info.value.detail
    
@pytest.mark.asyncio
async def test_list_expenses_via_http_includes_splits(client: AsyncClient):
    owner = await client.post(
        "/api/v1/auth/register",
        json={"email": "listexp@example.com", "password": "TestPass123", "display_name": "Owner"},
    )
    headers = {"Authorization": f"Bearer {owner.json()['tokens']['access_token']}"}

    trip_resp = await client.post(
        "/api/v1/trips",
        json={"name": "List Test", "destination": "X", "start_date": "2026-12-01", "end_date": "2026-12-05", "base_currency": "USD"},
        headers=headers,
    )
    trip_id = trip_resp.json()["id"]

    members_resp = await client.get(f"/api/v1/trips/{trip_id}/members", headers=headers)
    member_id = members_resp.json()[0]["id"]

    categories_resp = await client.get("/api/v1/categories")
    category_id = categories_resp.json()[0]["id"]

    await client.post(
        f"/api/v1/trips/{trip_id}/expenses",
        json={
            "category_id": category_id, "paid_by": member_id, "amount": 50.00, "currency": "USD",
            "split_type": "equal", "split_between": [member_id],
            "expense_date": "2026-12-02", "client_uuid": "11111111-1111-1111-1111-111111111111",
        },
        headers=headers,
    )

    response = await client.get(f"/api/v1/trips/{trip_id}/expenses", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert len(response.json()[0]["splits"]) == 1
    

@pytest.mark.asyncio
async def test_list_expenses_orders_by_most_recently_created(client: AsyncClient):
    owner = await client.post(
        "/api/v1/auth/register",
        json={"email": "order1@example.com", "password": "TestPass123", "display_name": "Owner"},
    )
    headers = {"Authorization": f"Bearer {owner.json()['tokens']['access_token']}"}

    trip_resp = await client.post(
        "/api/v1/trips",
        json={"name": "Order Test", "destination": "X", "start_date": "2026-12-01", "end_date": "2026-12-05", "base_currency": "USD"},
        headers=headers,
    )
    trip_id = trip_resp.json()["id"]
    member_id = (await client.get(f"/api/v1/trips/{trip_id}/members", headers=headers)).json()[0]["id"]
    category_id = (await client.get("/api/v1/categories")).json()[0]["id"]

    # Same expense_date for both, deliberately -- this is exactly the case
    # that broke ordering before the fix.
    await client.post(
        f"/api/v1/trips/{trip_id}/expenses",
        json={
            "category_id": category_id, "paid_by": member_id, "amount": 10.00, "currency": "USD",
            "split_type": "equal", "split_between": [member_id],
            "expense_date": "2026-12-02", "client_uuid": "22222222-2222-2222-2222-222222222222",
            "notes": "First",
        },
        headers=headers,
    )
    await client.post(
        f"/api/v1/trips/{trip_id}/expenses",
        json={
            "category_id": category_id, "paid_by": member_id, "amount": 20.00, "currency": "USD",
            "split_type": "equal", "split_between": [member_id],
            "expense_date": "2026-12-02", "client_uuid": "33333333-3333-3333-3333-333333333333",
            "notes": "Second",
        },
        headers=headers,
    )

    response = await client.get(f"/api/v1/trips/{trip_id}/expenses", headers=headers)
    notes_in_order = [e["notes"] for e in response.json()]
    assert notes_in_order == ["Second", "First"]
    
def test_calculate_equal_splits_payer_excluded_no_remainder():
    from app.services.expense_service import calculate_equal_splits
    import uuid as uuid_module

    payer = uuid_module.uuid4()
    a, b, c, d = uuid_module.uuid4(), uuid_module.uuid4(), uuid_module.uuid4(), uuid_module.uuid4()

    # Payer not in the participant list -- this used to raise KeyError.
    splits = calculate_equal_splits(Decimal("1000.00"), [a, b, c, d], payer)

    assert payer not in splits
    assert sum(splits.values()) == Decimal("1000.00")
    assert all(v == Decimal("250.00") for v in splits.values())


def test_calculate_equal_splits_payer_excluded_with_remainder():
    from app.services.expense_service import calculate_equal_splits
    import uuid as uuid_module

    payer = uuid_module.uuid4()
    a, b, c = uuid_module.uuid4(), uuid_module.uuid4(), uuid_module.uuid4()

    # 1000 / 3 doesn't divide evenly -- remainder must go to the first
    # participant (a), since the payer isn't in the split at all.
    splits = calculate_equal_splits(Decimal("1000.00"), [a, b, c], payer)

    assert payer not in splits
    assert sum(splits.values()) == Decimal("1000.00")
    assert splits[a] == Decimal("333.34")
    assert splits[b] == Decimal("333.33")
    assert splits[c] == Decimal("333.33")