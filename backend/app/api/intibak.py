from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.database import get_db
from app.core.dependencies import require_role
from app.core.storage import MinIOClient, get_minio_client
from app.domain.enums import UserRole
from app.services.intibak_service import IntibakService

router = APIRouter()
_require_ygk = require_role(UserRole.TRANSFER_COMMISSION)


@router.post("/intibak/{table_id}/parse-transcript")
async def parse_transcript(
    table_id: uuid.UUID,
    current_user=Depends(_require_ygk),
    db: AsyncSession = Depends(get_db),
    storage: MinIOClient = Depends(get_minio_client),
):
    """
    Parse the applicant's transcript PDF and return a structured course list.

    - On the first call the PDF is fetched from MinIO, parsed with pdfplumber,
      and the result is saved to Document.extracted_data (JSONB).
    - If the same transcript was previously parsed and confirmed by the commission
      (extraction_confirmed=True) the cached result is returned directly.
    - The commission then uses POST /intibak/{table_id}/mappings to map the
      parsed courses to the target program's curriculum.

    Example response::

        {
          "document_id": "3fa85f64-...",
          "parser_strategy": "table",
          "warnings": [],
          "courses": [
            {
              "course_code": "MAT101",
              "course_name": "Calculus I",
              "credits": 4.0,
              "grade": "AA",
              "semester": "2022-2023 Fall"
            }
          ]
        }
    """
    svc = IntibakService(db)
    return await svc.parse_transcript_for_table(
        table_id=table_id,
        requester_id=current_user.id,
        storage=storage,
    )
