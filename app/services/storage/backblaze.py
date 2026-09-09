import asyncio
import logging

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.exceptions import UploadError
from app.services.storage.base import StorageService

logger = logging.getLogger(__name__)

PRESIGNED_URL_EXPIRATION_SECONDS = 3600


class B2StorageService(StorageService):
    """Stores files in a private Backblaze B2 bucket.

    Uses the S3-compatible API so the same code also works with other
    S3-compatible providers (Cloudflare R2, MinIO, ...) by swapping the
    endpoint URL.
    """

    def __init__(
        self,
        endpoint_url: str,
        key_id: str,
        application_key: str,
        bucket: str,
        region: str = "us-west-004",
    ):
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=key_id,
            aws_secret_access_key=application_key,
            region_name=region,
            config=BotoConfig(signature_version="s3v4"),
        )
        self.bucket = bucket

    async def save(self, key: str, data: bytes, content_type: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.put_object,
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except (ClientError, BotoCoreError) as exc:
            logger.error("B2 upload failed for %s: %s", key, exc)
            raise UploadError("Failed to upload video to storage") from exc

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.delete_object, Bucket=self.bucket, Key=key
            )
        except (ClientError, BotoCoreError) as exc:
            logger.error("B2 delete failed for %s: %s", key, exc)
            raise UploadError("Failed to delete video from storage") from exc

    async def read(self, key: str) -> bytes:
        try:
            return await asyncio.to_thread(self._get_object, key)
        except (ClientError, BotoCoreError) as exc:
            logger.error("B2 read failed for %s: %s", key, exc)
            raise UploadError("Failed to read video from storage") from exc

    def _get_object(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        try:
            return response["Body"].read()
        finally:
            response["Body"].close()

    def get_url(self, key: str) -> str | None:
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=PRESIGNED_URL_EXPIRATION_SECONDS,
            )
        except (ClientError, BotoCoreError) as exc:
            logger.error("B2 presigned URL generation failed for %s: %s", key, exc)
            raise UploadError("Failed to generate video URL") from exc
