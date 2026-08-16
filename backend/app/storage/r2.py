"""Cloudflare R2 storage (S3-compatible, via boto3).

R2 object PUT is already atomic — a GET returns either the complete previous
object or the complete new one, never a partial body — so ``put_atomic`` is just
``put``. boto3 is imported lazily so the dev/local path has no hard dependency on
AWS libraries at import time.
"""
from __future__ import annotations

from typing import Optional


class R2Storage:
    def __init__(
        self,
        endpoint_url: Optional[str],
        access_key_id: Optional[str],
        secret_access_key: Optional[str],
        bucket: Optional[str],
        public_base_url: str,
    ):
        if not all([endpoint_url, access_key_id, secret_access_key, bucket]):
            raise ValueError("R2 storage requires endpoint_url, access_key_id, secret_access_key, bucket")
        import boto3  # lazy: only needed when STORAGE_BACKEND=r2

        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",  # R2 uses "auto"
        )

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return key

    # R2/S3 PUT is atomic at the object level; no temp-then-rename needed.
    put_atomic = put

    def get(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def url(self, key: str) -> str:
        return f"{self.public_base_url}/{key.lstrip('/')}"
