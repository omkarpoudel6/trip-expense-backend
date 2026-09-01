from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import RegisterTokenRequest
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.post("/register-token", status_code=204)
async def register_token(
    payload: RegisterTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await notification_service.register_token(db, current_user.id, payload.token, payload.platform)
    
@router.delete("/register-token", status_code=204)
async def unregister_token(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await notification_service.unregister_token(db, token)