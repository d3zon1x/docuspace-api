from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import Settings
from app.errors import DocumentNotFoundError


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._region = settings.s3_region
        self._is_prod = settings.app_env == "prod"

        client_kwargs: dict[str, Any] = {
            "region_name": settings.s3_region,
        }
        if not self._is_prod and settings.s3_endpoint_url:
            client_kwargs["endpoint_url"] = settings.s3_endpoint_url

        if (
            settings.aws_access_key_id
            and settings.aws_secret_access_key
            and not (self._is_prod and settings.aws_access_key_id == "test")
        ):
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        self._client = boto3.client("s3", **client_kwargs)
        self._bucket_ensured = self._is_prod

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
            raise DocumentNotFoundError("Document content not found in storage") from exc

    def delete(self, *, key: str) -> None:
        self._ensure_bucket()
        self._client.delete_object(Bucket=self._bucket, Key=key)


class InMemoryStorage:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def upload(self, *, key: str, data: bytes, content_type: str) -> None:
        self._objects[key] = data

    def download(self, *, key: str) -> bytes:
        if key not in self._objects:
            raise DocumentNotFoundError("Document content not found in storage")
        return self._objects[key]

    def delete(self, *, key: str) -> None:
        self._objects.pop(key, None)


StorageBackend = S3Storage | InMemoryStorage
