from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_token, hash_password, token_fingerprint, verify_password
from app.models.session import UserSession
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db, self.users = db, UserRepository(db)

    async def register(self, data: RegisterRequest) -> User:
        if await self.users.by_email(data.email):
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
        user = await self.users.create(name=data.name, email=data.email, password_hash=hash_password(data.password))
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, data: LoginRequest) -> User:
        user = await self.users.by_email(data.email)
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
        return user

    async def issue_tokens(self, user: User) -> tuple[str, str]:
        access, _ = create_token(user.id, "access", timedelta(minutes=settings.access_token_expire_minutes))
        refresh, expires = create_token(user.id, "refresh", timedelta(days=settings.refresh_token_expire_days))
        self.db.add(UserSession(user_id=user.id, token_hash=token_fingerprint(refresh), expires_at=expires, created_at=datetime.now(timezone.utc)))
        await self.db.commit()
        return access, refresh

    async def rotate_refresh(self, refresh: str) -> tuple[User, str, str]:
        from app.core.security import decode_token
        try: user_id = decode_token(refresh, "refresh")
        except Exception: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
        session = await self.db.scalar(select(UserSession).where(UserSession.token_hash == token_fingerprint(refresh)))
        if not session or session.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
        user = await self.users.by_id(user_id)
        if not user or not user.is_active: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
        await self.db.delete(session)
        access, new_refresh = await self.issue_tokens(user)
        return user, access, new_refresh

    async def logout(self, refresh: str | None) -> None:
        if refresh:
            await self.db.execute(delete(UserSession).where(UserSession.token_hash == token_fingerprint(refresh)))
            await self.db.commit()
