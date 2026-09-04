from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

Db = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(db: Db, access_token: Annotated[str | None, Cookie()] = None) -> User:
    if not access_token: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try: user_id = decode_token(access_token, "access")
    except (jwt.InvalidTokenError, ValueError): raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    user = await UserRepository(db).by_id(user_id)
    if not user or not user.is_active: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid account")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN: raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
