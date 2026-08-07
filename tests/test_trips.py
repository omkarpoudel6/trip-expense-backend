"""
Trip management tests: create/get/update/archive, invite/join, leave,
and remove-member -- covering the RBAC rules from Milestone 2's spec.
"""
import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str, name: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPass123", "display_name": name},
    )
    return response.json()


def _auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def valid_trip_payload() -> dict:
    return {
        "name": "Bali Adventure",
        "destination": "Bali, Indonesia",
        "start_date": "2026-09-01",
        "end_date": "2026-09-10",
        "base_currency": "USD",
    }


@pytest.mark.asyncio
async def test_create_trip_success(client: AsyncClient, valid_trip_payload: dict):
    auth = await _register_and_login(client, "creator@example.com", "Creator")
    response = await client.post(
        "/api/v1/trips", json=valid_trip_payload, headers=_auth_headers(auth["tokens"])
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Bali Adventure"
    assert response.json()["status"] == "active"


@pytest.mark.asyncio
async def test_create_trip_requires_auth(client: AsyncClient, valid_trip_payload: dict):
    response = await client.post("/api/v1/trips", json=valid_trip_payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_trip_denied_for_non_member(client: AsyncClient, valid_trip_payload: dict):
    owner = await _register_and_login(client, "owner@example.com", "Owner")
    create_resp = await client.post(
        "/api/v1/trips", json=valid_trip_payload, headers=_auth_headers(owner["tokens"])
    )
    trip_id = create_resp.json()["id"]

    outsider = await _register_and_login(client, "outsider@example.com", "Outsider")
    response = await client.get(f"/api/v1/trips/{trip_id}", headers=_auth_headers(outsider["tokens"]))

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_trip_denied_for_non_admin(client: AsyncClient, valid_trip_payload: dict):
    owner = await _register_and_login(client, "owner2@example.com", "Owner")
    create_resp = await client.post(
        "/api/v1/trips", json=valid_trip_payload, headers=_auth_headers(owner["tokens"])
    )
    trip_id = create_resp.json()["id"]

    invite_resp = await client.post(
        f"/api/v1/trips/{trip_id}/invites", headers=_auth_headers(owner["tokens"])
    )
    code = invite_resp.json()["code"]

    member = await _register_and_login(client, "member2@example.com", "Member")
    await client.post("/api/v1/trips/join", json={"code": code}, headers=_auth_headers(member["tokens"]))

    response = await client.patch(
        f"/api/v1/trips/{trip_id}", json={"name": "Hijacked Name"}, headers=_auth_headers(member["tokens"])
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_trip_partial_update_by_admin(client: AsyncClient, valid_trip_payload: dict):
    owner = await _register_and_login(client, "owner3@example.com", "Owner")
    create_resp = await client.post(
        "/api/v1/trips", json=valid_trip_payload, headers=_auth_headers(owner["tokens"])
    )
    trip_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/v1/trips/{trip_id}", json={"budget": 1500}, headers=_auth_headers(owner["tokens"])
    )

    assert response.status_code == 200
    assert response.json()["budget"] == 1500.0
    assert response.json()["name"] == "Bali Adventure"  # unchanged


@pytest.mark.asyncio
async def test_archive_trip_by_admin(client: AsyncClient, valid_trip_payload: dict):
    owner = await _register_and_login(client, "owner4@example.com", "Owner")
    create_resp = await client.post(
        "/api/v1/trips", json=valid_trip_payload, headers=_auth_headers(owner["tokens"])
    )
    trip_id = create_resp.json()["id"]

    response = await client.post(
        f"/api/v1/trips/{trip_id}/archive", headers=_auth_headers(owner["tokens"])
    )
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_invite_and_join_flow(client: AsyncClient, valid_trip_payload: dict):
    owner = await _register_and_login(client, "owner5@example.com", "Owner")
    create_resp = await client.post(
        "/api/v1/trips", json=valid_trip_payload, headers=_auth_headers(owner["tokens"])
    )
    trip_id = create_resp.json()["id"]

    invite_resp = await client.post(
        f"/api/v1/trips/{trip_id}/invites", headers=_auth_headers(owner["tokens"])
    )
    assert invite_resp.status_code == 201
    code = invite_resp.json()["code"]
    assert len(code) == 8

    joiner = await _register_and_login(client, "joiner5@example.com", "Joiner")
    join_resp = await client.post(
        "/api/v1/trips/join", json={"code": code}, headers=_auth_headers(joiner["tokens"])
    )
    assert join_resp.status_code == 200
    assert join_resp.json()["id"] == trip_id


@pytest.mark.asyncio
async def test_join_with_invalid_code_returns_404(client: AsyncClient):
    joiner = await _register_and_login(client, "joiner6@example.com", "Joiner")
    response = await client.post(
        "/api/v1/trips/join", json={"code": "BADCODE1"}, headers=_auth_headers(joiner["tokens"])
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invite_creation_denied_for_non_admin(client: AsyncClient, valid_trip_payload: dict):
    owner = await _register_and_login(client, "owner7@example.com", "Owner")
    create_resp = await client.post(
        "/api/v1/trips", json=valid_trip_payload, headers=_auth_headers(owner["tokens"])
    )
    trip_id = create_resp.json()["id"]

    invite_resp = await client.post(
        f"/api/v1/trips/{trip_id}/invites", headers=_auth_headers(owner["tokens"])
    )
    code = invite_resp.json()["code"]

    member = await _register_and_login(client, "member7@example.com", "Member")
    await client.post("/api/v1/trips/join", json={"code": code}, headers=_auth_headers(member["tokens"]))

    response = await client.post(
        f"/api/v1/trips/{trip_id}/invites", headers=_auth_headers(member["tokens"])
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_leave_trip(client: AsyncClient, valid_trip_payload: dict):
    owner = await _register_and_login(client, "owner8@example.com", "Owner")
    create_resp = await client.post(
        "/api/v1/trips", json=valid_trip_payload, headers=_auth_headers(owner["tokens"])
    )
    trip_id = create_resp.json()["id"]

    invite_resp = await client.post(
        f"/api/v1/trips/{trip_id}/invites", headers=_auth_headers(owner["tokens"])
    )
    code = invite_resp.json()["code"]

    member = await _register_and_login(client, "member8@example.com", "Member")
    await client.post("/api/v1/trips/join", json={"code": code}, headers=_auth_headers(member["tokens"]))

    leave_resp = await client.post(
        f"/api/v1/trips/{trip_id}/leave", headers=_auth_headers(member["tokens"])
    )
    assert leave_resp.status_code == 204

    # After leaving, member should no longer have access
    get_resp = await client.get(f"/api/v1/trips/{trip_id}", headers=_auth_headers(member["tokens"]))
    assert get_resp.status_code == 403
    

@pytest.mark.asyncio
async def test_remove_member_blocked_with_outstanding_balance(db_session):
    from sqlalchemy import select
    from app.models.category import Category
    from app.models.trip_member import TripMember
    from app.schemas.auth import RegisterRequest
    from app.schemas.expense import CreateExpenseRequest
    from app.schemas.trip import CreateTripRequest
    from app.services import auth_service, expense_service, trip_invite_service, trip_service
    from fastapi import HTTPException
    import uuid as uuid_module

    owner = await auth_service.register_user(
        db_session, RegisterRequest(email="rmowner3@example.com", password="TestPass123", display_name="Owner")
    )
    member = await auth_service.register_user(
        db_session, RegisterRequest(email="rmmember3@example.com", password="TestPass123", display_name="Member")
    )
    trip = await trip_service.create_trip(
        db_session, owner.id,
        CreateTripRequest(name="Remove Test", destination="X", start_date="2026-12-01", end_date="2026-12-05", base_currency="USD"),
    )
    invite = await trip_invite_service.create_invite(db_session, trip.id, owner.id)
    await trip_invite_service.join_trip_by_code(db_session, invite.code, member.id)

    members_result = await db_session.execute(select(TripMember).where(TripMember.trip_id == trip.id))
    m = {tm.user_id: tm.id for tm in members_result.scalars().all()}

    category = (await db_session.execute(select(Category).where(Category.name == "Food"))).scalars().first()
    await expense_service.create_expense(
        db_session, trip.id, owner.id,
        CreateExpenseRequest(
            category_id=category.id, paid_by=m[owner.id], amount=100.00, currency="USD",
            split_type="equal", split_between=[m[owner.id], m[member.id]],
            expense_date="2026-12-02", client_uuid=uuid_module.uuid4(),
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await trip_service.remove_member(db_session, trip.id, owner.id, m[member.id])

    assert exc_info.value.status_code == 409
    assert "outstanding balance" in exc_info.value.detail


@pytest.mark.asyncio
async def test_remove_member_succeeds_with_zero_balance(db_session):
    from sqlalchemy import select
    from app.models.trip_member import TripMember
    from app.schemas.auth import RegisterRequest
    from app.schemas.trip import CreateTripRequest
    from app.services import auth_service, trip_invite_service, trip_service

    owner = await auth_service.register_user(
        db_session, RegisterRequest(email="rmowner4@example.com", password="TestPass123", display_name="Owner")
    )
    member = await auth_service.register_user(
        db_session, RegisterRequest(email="rmmember4@example.com", password="TestPass123", display_name="Member")
    )
    trip = await trip_service.create_trip(
        db_session, owner.id,
        CreateTripRequest(name="Remove Test 2", destination="X", start_date="2026-12-01", end_date="2026-12-05", base_currency="USD"),
    )
    invite = await trip_invite_service.create_invite(db_session, trip.id, owner.id)
    await trip_invite_service.join_trip_by_code(db_session, invite.code, member.id)

    members_result = await db_session.execute(select(TripMember).where(TripMember.trip_id == trip.id))
    m = {tm.user_id: tm.id for tm in members_result.scalars().all()}

    # No expenses -- zero balance, removal should succeed without error.
    await trip_service.remove_member(db_session, trip.id, owner.id, m[member.id])