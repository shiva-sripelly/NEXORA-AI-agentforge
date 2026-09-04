from typing import Annotated

from fastapi import APIRouter, Cookie, Response, status

from app.api.dependencies import CurrentUser, Db
from app.core.config import settings
from app.schemas.auth import AuthResponse, LoginRequest, MessageResponse, RegisterRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def set_cookies(response: Response, access: str, refresh: str) -> None:
    common = {"httponly": True, "secure": settings.cookie_secure, "samesite": settings.cookie_samesite}
    response.set_cookie("access_token", access, max_age=settings.access_token_expire_minutes * 60, path="/", **common)
    response.set_cookie("refresh_token", refresh, max_age=settings.refresh_token_expire_days * 86400, path="/api/auth", **common)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, response: Response, db: Db):
    service = AuthService(db); user = await service.register(data); access, refresh = await service.issue_tokens(user)
    set_cookies(response, access, refresh); return AuthResponse(user=user)


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest, response: Response, db: Db):
    service = AuthService(db); user = await service.authenticate(data); access, refresh = await service.issue_tokens(user)
    set_cookies(response, access, refresh); return AuthResponse(user=user)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(response: Response, db: Db, refresh_token: Annotated[str | None, Cookie()] = None):
    if not refresh_token: from fastapi import HTTPException; raise HTTPException(401, "Refresh token missing")
    user, access, new_refresh = await AuthService(db).rotate_refresh(refresh_token)
    set_cookies(response, access, new_refresh); return AuthResponse(user=user)


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response, db: Db, refresh_token: Annotated[str | None, Cookie()] = None):
    await AuthService(db).logout(refresh_token)
    response.delete_cookie("access_token", path="/"); response.delete_cookie("refresh_token", path="/api/auth")
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=AuthResponse)
async def me(user: CurrentUser): return AuthResponse(user=user)
