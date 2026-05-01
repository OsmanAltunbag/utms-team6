import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user import Applicant, User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return await self.db.get(User, user_id)

    async def get_by_national_id(self, national_id: str) -> Optional[Applicant]:
        result = await self.db.execute(
            select(Applicant).where(Applicant.national_id == national_id)
        )
        return result.scalar_one_or_none()

    async def save(self, user: User) -> None:
        self.db.add(user)
        await self.db.flush()
