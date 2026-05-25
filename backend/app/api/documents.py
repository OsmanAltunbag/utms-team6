import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.storage import MinIOClient, get_minio_client
from app.domain.document import Document
from app.domain.user import User

router = APIRouter()


@router.get("/{document_id}/stream")
async def stream_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: MinIOClient = Depends(get_minio_client),
) -> StreamingResponse:
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        response = storage.get_object(doc.file_path)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found in storage")

    file_name = doc.file_name or "document.pdf"
    return StreamingResponse(
        response,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{file_name}"'},
    )
