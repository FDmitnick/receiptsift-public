from __future__ import annotations

from pathlib import Path
from typing import Protocol

try:
    import boto3
except ImportError:  # pragma: no cover - installed by production requirements
    boto3 = None  # type: ignore[assignment]


class ObjectStoreError(RuntimeError):
    pass


class ObjectStore(Protocol):
    def put(self, key: str, payload: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


def _safe_key(key: str) -> str:
    if len(key) != 32 or any(character not in "0123456789abcdef" for character in key):
        raise ObjectStoreError("invalid_object_key")
    return key


class LocalObjectStore:
    """Private local object storage for development and single-replica beta use."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = _safe_key(key)
        return self.root / safe[:2] / f"{safe}.bin"

    def put(self, key: str, payload: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as error:
            raise ObjectStoreError("object_not_found") from error

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3ObjectStore:
    """S3-compatible private storage for AWS S3, Cloudflare R2, and similar providers."""

    def __init__(
        self,
        bucket: str,
        *,
        endpoint_url: str = "",
        region: str = "auto",
        access_key_id: str = "",
        secret_access_key: str = "",
        prefix: str = "receipt-sources",
    ) -> None:
        if boto3 is None:
            raise ObjectStoreError("boto3_not_installed")
        if not bucket:
            raise ObjectStoreError("object_store_bucket_required")
        self.bucket = bucket
        self.prefix = prefix.strip("/") or "receipt-sources"
        options: dict[str, str] = {"region_name": region or "auto"}
        if endpoint_url:
            options["endpoint_url"] = endpoint_url
        if access_key_id:
            options["aws_access_key_id"] = access_key_id
        if secret_access_key:
            options["aws_secret_access_key"] = secret_access_key
        self.client = boto3.client("s3", **options)

    def _object_name(self, key: str) -> str:
        safe = _safe_key(key)
        return f"{self.prefix}/{safe[:2]}/{safe}.bin"

    def put(self, key: str, payload: bytes) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=self._object_name(key),
                Body=payload,
                ContentType="application/octet-stream",
                CacheControl="no-store",
            )
        except Exception as error:  # provider SDK exceptions do not share a stable base class
            raise ObjectStoreError("object_write_failed") from error

    def get(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._object_name(key))
            return response["Body"].read()
        except Exception as error:  # provider SDK exceptions do not share a stable base class
            raise ObjectStoreError("object_read_failed") from error

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._object_name(key))
        except Exception as error:  # provider SDK exceptions do not share a stable base class
            raise ObjectStoreError("object_delete_failed") from error
