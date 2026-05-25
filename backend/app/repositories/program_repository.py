import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.program import Program


class ProgramRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, program_id: uuid.UUID) -> Optional[Program]:
        return await self.db.get(Program, program_id)
