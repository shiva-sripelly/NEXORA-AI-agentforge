from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession): self.db = db

    async def by_email(self, email: str) -> User | None:
        return await self.db.scalar(select(User).where(User.email == email.lower()))

    async def by_id(self, user_id: UUID) -> User | None:
        return await self.db.get(User, user_id)

    async def create(self, *, name: str, email: str, password_hash: str) -> User:
        user = User(name=name.strip(), email=email.lower(), password_hash=password_hash)
        self.db.add(user)
        await self.db.flush()
        return user
