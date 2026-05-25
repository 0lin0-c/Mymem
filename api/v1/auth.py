import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from schemas.auth_schema import AuthResponse, LoginRequest
from services.user_account_service import UserAccountService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["认证"])


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    logger.info("Login request: username=%s", request.username)
    service = UserAccountService(session)
    return AuthResponse(**await service.login(request.username, request.password))


@router.post("/logout")
async def logout(
    user_id: str,
    session_id: str | None = None,
):
    UserAccountService(session=None).logout(user_id, session_id)
    return {"success": True, "message": "Logout successful"}
