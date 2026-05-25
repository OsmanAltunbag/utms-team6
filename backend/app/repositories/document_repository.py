import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.document import Document


class DocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, doc_id: uuid.UUID) -> Optional[Document]:
        return await self.db.get(Document, doc_id)

    async def get_by_application(self, application_id: uuid.UUID) -> List[Document]:
        result = await self.db.execute(
            select(Document).where(Document.application_id == application_id)
        )
        return list(result.scalars().all())

    async def save(self, document: Document) -> None:
        self.db.add(document)
        await self.db.flush()
