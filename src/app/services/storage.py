from typing import Protocol

import boto3
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.core.errors import NotFoundError


class StorageServiceProtocol(Protocol):
    def upload(self, *, key: str, data: bytes, content_type: str) -> None: ...

    def download(self, *, key: str) -> bytes: ...

    def delete(self, *, key: str) -> None: ...


class S3StorageService(StorageServiceProtocol):
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._region = settings.s3_region
        self._client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self._bucket_ensured = False

    def _ensure_bucket(self) -> None:
        if self._bucket_ensured:
            return
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            if self._region == "us-east-1":
                self._client.create_bucket(Bucket=self._bucket)
            else:
                self._client.create_bucket(
                    Bucket=self._bucket,
                    CreateBucketConfiguration={"LocationConstraint": self._region},  # type: ignore[typeddict-item]
                )
        self._bucket_ensured = True

    def upload(self, *, key: str, data: bytes, content_type: str) -> None:
        self._ensure_bucket()
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def download(self, *, key: str) -> bytes:
        self._ensure_bucket()
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return bytes(response["Body"].read())
        except ClientError as exc:
            raise NotFoundError(
                "Document content not found in storage.",
                code="DOCUMENT_STORAGE_NOT_FOUND",
            ) from exc

    def delete(self, *, key: str) -> None:
        self._ensure_bucket()
        self._client.delete_object(Bucket=self._bucket, Key=key)


class InMemoryStorageService(StorageServiceProtocol):
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def upload(self, *, key: str, data: bytes, content_type: str) -> None:
        _ = content_type
        self._objects[key] = data

    def download(self, *, key: str) -> bytes:
        if key not in self._objects:
            raise NotFoundError(
                "Document content not found in storage.",
                code="DOCUMENT_STORAGE_NOT_FOUND",
            )
        return self._objects[key]

    def delete(self, *, key: str) -> None:
        self._objects.pop(key, None)
