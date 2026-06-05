import uuid
from typing import List, Optional

from sqlalchemy import case, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.document import Document
from app.domain.enums import DocStatus, DocType


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

    async def get_transcript_for_application(
        self,
        application_id: uuid.UUID,
    ) -> Optional[Document]:
        """
        Return the most recent transcript document for the given application.

        Priority order:
          1. ACCEPTED documents (preferred — already verified by staff)
          2. PENDING documents  (fallback — uploaded but not yet reviewed)

        Returns None if no transcript has been uploaded.
        """
        result = await self.db.execute(
            select(Document)
            .where(
                Document.application_id == application_id,
                Document.doc_type == DocType.TRANSCRIPT,
                Document.status.in_([DocStatus.ACCEPTED, DocStatus.PENDING]),
            )
            .order_by(
                # ACCEPTED rows sort first (0), PENDING rows sort second (1)
                case(
                    (Document.status == DocStatus.ACCEPTED, 0),
                    else_=1,
                ),
                Document.uploaded_at.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()
