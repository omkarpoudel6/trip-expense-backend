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