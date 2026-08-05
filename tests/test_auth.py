"""
Auth endpoint tests. These map directly to Milestone 1's acceptance
criteria: register/login/refresh works, 90%+ coverage on the auth module.
"""
import pytest
from httpx import AsyncClient

from app.core.security import create_refresh_token
from app.models.user import AuthProvider, User


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, valid_register_payload: dict):
    response = await client.post("/api/v1/auth/register", json=valid_register_payload)

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == valid_register_payload["email"]
    assert "access_token" in body["tokens"]
    assert "refresh_token" in body["tokens"]


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client: AsyncClient, valid_register_payload: dict):
    await client.post("/api/v1/auth/register", json=valid_register_payload)
    response = await client.post("/api/v1/auth/register", json=valid_register_payload)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password_rejected(client: AsyncClient):
    payload = {"email": "weak@example.com", "password": "alllowercase", "display_name": "Weak"}
    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, valid_register_payload: dict):
    await client.post("/api/v1/auth/register", json=valid_register_payload)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": valid_register_payload["email"], "password": valid_register_payload["password"]},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()["tokens"]


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient, valid_register_payload: dict):
    await client.post("/api/v1/auth/register", json=valid_register_payload)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": valid_register_payload["email"], "password": "WrongPass123"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401_not_404(client: AsyncClient):
    """Same error as wrong password -- prevents account enumeration."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "WhoKnows123"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_issues_new_token_pair(client: AsyncClient, valid_register_payload: dict):
    register_response = await client.post("/api/v1/auth/register", json=valid_register_payload)
    original_refresh_token = register_response.json()["tokens"]["refresh_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh_token})

    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["access_token"] != register_response.json()["tokens"]["access_token"]
    assert new_tokens["refresh_token"] != original_refresh_token


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(client: AsyncClient, valid_register_payload: dict):
    """An access token must never be usable where a refresh token is expected."""
    register_response = await client.post("/api/v1/auth/register", json=valid_register_payload)
    access_token = register_response.json()["tokens"]["access_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_authentication(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_me_returns_current_user(client: AsyncClient, valid_register_payload: dict):
    register_response = await client.post("/api/v1/auth/register", json=valid_register_payload)
    access_token = register_response.json()["tokens"]["access_token"]

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == valid_register_payload["email"]
    
    
@pytest.mark.asyncio
async def test_me_with_invalid_token_returns_401(client: AsyncClient):
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_social_only_account_returns_401(client: AsyncClient, db_session):
    """A user who signed up via Google has no password_hash -- logging in
    with email/password must fail cleanly, not crash."""
    social_user = User(
        email="socialuser@example.com",
        password_hash=None,
        display_name="Social User",
        auth_provider=AuthProvider.GOOGLE,
    )
    db_session.add(social_user)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "socialuser@example.com", "password": "AnyPassword123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_for_nonexistent_user_returns_401(client: AsyncClient):
    """A structurally valid refresh token signed for a user ID that
    doesn't exist in the database must be rejected, not crash."""
    fake_user_id = "00000000-0000-0000-0000-000000000000"
    token = create_refresh_token(fake_user_id)

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401




