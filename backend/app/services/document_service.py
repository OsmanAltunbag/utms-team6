import uuid

from dataclasses import dataclass

from typing import Any, Optional



from fastapi import HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession



from app.core.storage import MinIOClient

from app.domain.document import Document

from app.domain.enums import DocStatus, DocType

from app.repositories.application_repository import ApplicationRepository

from app.repositories.document_repository import DocumentRepository



_MAX_FILE_SIZE = 5_242_880  # 5 MB

_PDF_MIME = "application/pdf"

_IMAGE_MIMES = {"image/jpeg", "image/png", "image/jpg"}

_ALLOWED_MIMES = {_PDF_MIME, *_IMAGE_MIMES}

_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}





def resolve_content_type(file_name: str, stored_type: str | None = None) -> str:

    if stored_type and stored_type in _ALLOWED_MIMES:

        return "image/jpeg" if stored_type == "image/jpg" else stored_type

    lower = file_name.lower()

    if lower.endswith(".png"):

        return "image/png"

    if lower.endswith((".jpg", ".jpeg")):

        return "image/jpeg"

    return _PDF_MIME





def is_allowed_upload(file_name: str, content_type: str | None = None) -> bool:

    if content_type:

        normalized = "image/jpeg" if content_type == "image/jpg" else content_type

        if normalized in _ALLOWED_MIMES:

            return True

    return any(file_name.lower().endswith(ext) for ext in _ALLOWED_EXTENSIONS)





@dataclass

class PresignedUploadResult:

    upload_url: str

    object_key: str





class DocumentService:

    def __init__(self, db: AsyncSession, storage: Optional[MinIOClient] = None) -> None:

        self.db = db

        self._doc_repo = DocumentRepository(db)

        self._app_repo = ApplicationRepository(db)

        self._storage = storage or MinIOClient()



    async def generate_upload_url(

        self, application_id: uuid.UUID, doc_type: DocType

    ) -> PresignedUploadResult:

        application = await self._app_repo.get_by_id(application_id)

        if application is None:

            raise HTTPException(status_code=404, detail="Application not found")



        object_key = (

            f"applications/{application_id}/{doc_type.value}/{uuid.uuid4()}.pdf"

        )

        upload_url = self._storage.generate_presigned_put(object_key, ttl=300)

        return PresignedUploadResult(upload_url=upload_url, object_key=object_key)



    async def confirm_upload(

        self,

        application_id: uuid.UUID,

        doc_type: DocType,

        object_key: str,

        file_name: str,

        file_size_bytes: int,

        extracted_data: Optional[Any] = None,

    ) -> Document:

        if file_size_bytes > _MAX_FILE_SIZE:

            raise HTTPException(

                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,

                detail="File exceeds 5 MB limit.",

            )



        try:

            meta = self._storage.get_object_metadata(object_key)

            content_type = meta.get("content_type", "")

            if not is_allowed_upload(file_name, content_type):

                raise HTTPException(

                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,

                    detail="Invalid file format. Please upload a PDF or image file (JPG/PNG).",

                )

        except HTTPException:

            raise

        except Exception:

            if not is_allowed_upload(file_name):

                raise HTTPException(

                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,

                    detail="Invalid file format. Please upload a PDF or image file (JPG/PNG).",

                )



        document = Document(

            application_id=application_id,

            doc_type=doc_type,

            file_path=object_key,

            file_name=file_name,

            file_size_bytes=file_size_bytes,

            status=DocStatus.PENDING,

            extracted_data=extracted_data,

            extraction_confirmed=False,

        )

        await self._doc_repo.save(document)

        return document



    async def generate_preview_url(

        self, document_id: uuid.UUID, caller_id: uuid.UUID

    ) -> str:

        preview_url, _, _ = await self.generate_preview_url_with_status(

            document_id, caller_id

        )

        return preview_url



    async def generate_preview_url_with_status(

        self, document_id: uuid.UUID, caller_id: uuid.UUID

    ) -> tuple[str, bool, str]:

        """Return presigned inline preview URL, viewable flag, and content type."""

        document = await self._doc_repo.get_by_id(document_id)

        if document is None:

            raise HTTPException(status_code=404, detail="Document not found")



        application = await self._app_repo.get_by_id(document.application_id)

        if application is None:

            raise HTTPException(status_code=404, detail="Application not found")



        if application.applicant_id != caller_id:

            from app.repositories.user_repository import UserRepository

            from app.domain.enums import UserRole

            user = await UserRepository(self.db).get_by_id(caller_id)

            if user is None or user.role == UserRole.APPLICANT:

                raise HTTPException(

                    status_code=status.HTTP_403_FORBIDDEN,

                    detail="You do not have permission to view this document",

                )



        content_type = self._document_content_type(document)

        viewable = self._storage.object_exists(document.file_path)

        url = self._storage.generate_presigned_get(

            document.file_path,

            ttl=300,

            inline=True,

            file_name=document.file_name,

        )

        return url, viewable, content_type



    def _document_content_type(self, document: Document) -> str:

        try:

            meta = self._storage.get_object_metadata(document.file_path)

            return resolve_content_type(

                document.file_name,

                meta.get("content_type"),

            )

        except Exception:

            return resolve_content_type(document.file_name)


