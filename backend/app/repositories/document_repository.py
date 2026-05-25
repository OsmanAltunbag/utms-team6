import uuid
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.document import Document
from app.domain.enums import DocType


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

    async def delete_by_type(self, application_id: uuid.UUID, doc_type: DocType) -> None:
        await self.db.execute(
            delete(Document).where(
                Document.application_id == application_id,
                Document.doc_type == doc_type,
            )
        )
        await self.db.flush()

    async def save(self, document: Document) -> None:
        self.db.add(document)
        await self.db.flush()
