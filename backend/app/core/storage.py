import io
from datetime import timedelta

from minio import Minio

from app.core.config import settings


class MinIOClient:
    def __init__(self) -> None:
        self._client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self._bucket = settings.MINIO_BUCKET

    def generate_presigned_put(self, object_key: str, ttl: int = 300) -> str:
        return self._client.presigned_put_object(
            self._bucket, object_key, expires=timedelta(seconds=ttl)
        )

    def generate_presigned_get(
        self,
        object_key: str,
        ttl: int = 300,
        *,
        inline: bool = False,
        file_name: str | None = None,
    ) -> str:
        response_headers: dict[str, str] | None = None
        if inline:
            disposition = "inline"
            if file_name:
                disposition = f'inline; filename="{file_name}"'
            response_headers = {"response-content-disposition": disposition}
        return self._client.presigned_get_object(
            self._bucket,
            object_key,
            expires=timedelta(seconds=ttl),
            response_headers=response_headers,
        )

    def object_exists(self, object_key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, object_key)
            return True
        except Exception:
            return False

    def get_object(self, object_key: str):
        return self._client.get_object(self._bucket, object_key)

    def put_object(self, object_key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            self._bucket, object_key, io.BytesIO(data), len(data), content_type=content_type
        )

    def get_object_metadata(self, object_key: str) -> dict:
        stat = self._client.stat_object(self._bucket, object_key)
        return {
            "content_type": stat.content_type,
            "size": stat.size,
            "etag": stat.etag,
        }


def get_minio_client() -> MinIOClient:
    return MinIOClient()
