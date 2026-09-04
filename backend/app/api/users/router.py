from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import require_admin
from app.models.user import User
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/admin-check", response_model=UserResponse)
async def admin_check(user: Annotated[User, Depends(require_admin)]): return user
