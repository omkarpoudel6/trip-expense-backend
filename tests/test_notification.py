import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_and_unregister_push_token(client: AsyncClient):
    owner = await client.post(
        "/api/v1/auth/register",
        json={"email": "push1@example.com", "password": "TestPass123", "display_name": "Owner"},
    )
    headers = {"Authorization": f"Bearer {owner.json()['tokens']['access_token']}"}

    reg = await client.post(
        "/api/v1/notifications/register-token",
        json={"token": "ExponentPushToken[abc123]", "platform": "android"},
        headers=headers,
    )
    assert reg.status_code == 204

    # Re-registering the same token (app reopen) must not error.
    reg2 = await client.post(
        "/api/v1/notifications/register-token",
        json={"token": "ExponentPushToken[abc123]", "platform": "android"},
        headers=headers,
    )
    assert reg2.status_code == 204

    unreg = await client.delete(
        "/api/v1/notifications/register-token?token=ExponentPushToken[abc123]", headers=headers
    )
    assert unreg.status_code == 204