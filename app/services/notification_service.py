import uuid
import httpx
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.push_token import PushToken

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

async def register_token(db: AsyncSession, user_id: uuid.UUID, token: str, platform: str) -> None:
    stmt = insert(PushToken).values(user_id=user_id, token=token, platform=platform)
    stmt = stmt.on_conflict_do_update(index_elements=["token"], set_={"user_id": user_id, "platform": platform})
    await db.execute(stmt)
    await db.commit()
    
async def unregister_token(db: AsyncSession, token: str) -> None:
    await db.execute(delete(PushToken).where(PushToken.token == token))
    await db.commit()
    
async def send_push_to_users(db: AsyncSession, user_ids: list[uuid.UUID], title: str, body: str, data: dict | None = None) -> None:
    """Fire-and-forget. Never raises -- a push failure must never fail the
    request (expense creation, settlement confirm) that triggered it."""
    if not user_ids:
        return
    try:
        result = await db.execute(select(PushToken.token).where(PushToken.user_id.in_(user_ids)))
        tokens = [row[0] for row in result.all()]
        if not tokens:
            return
        messages = [{"to": t, "title":title, "body": body, "data":data or {}} for t in tokens]
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(EXPO_PUSH_URL, json=messages)
    except Exception:
        pass