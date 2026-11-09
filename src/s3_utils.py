from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from src.errors import AccessDeniedError, InputError, OsmPipelineError, TransientError

logger = logging.getLogger(__name__)

_MISSING_CODES = {"404", "NoSuchKey", "NotFound", "NoSuchBucket"}
_ACCESS_DENIED_CODES = {
    "403",
    "AccessDenied",
    "AllAccessDisabled",
    "InvalidAccessKeyId",
    "SignatureDoesNotMatch",
}
_TRANSIENT_CODES = {
    "SlowDown",
    "RequestTimeout",
    "InternalError",
    "InternalFailure",
    "ServiceUnavailable",
    "Throttling",
    "ThrottlingException",
}


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def _translate_client_error(exc: ClientError, context: str) -> OsmPipelineError:
    code = _error_code(exc)
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    if code in _ACCESS_DENIED_CODES or status == 403:
        return AccessDeniedError(f"{context}: {exc}")
    if code in _TRANSIENT_CODES or (isinstance(status, int) and 500 <= status < 600):
        return TransientError(f"{context}: {exc}")
    # Preserve retry behavior for S3 errors not explicitly classified above.
    return TransientError(f"{context}: {exc}")


class S3Client:
    """Small, retry-aware wrapper around boto3 S3 used by the pipeline."""

    def __init__(
        self,
        region: str,
        max_attempts: int = 5,
        connect_timeout: float = 10.0,
        read_timeout: float = 300.0,
        client: Any | None = None,
    ) -> None:
        if client is not None:
            self._client = client
            return

        import boto3
        from botocore.config import Config

        self._client = boto3.client(
            "s3",
            region_name=region,
            config=Config(
                retries={"max_attempts": max_attempts, "mode": "standard"},
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
            ),
        )

    def download(self, bucket: str, key: str, destination: str | Path) -> Path:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._client.download_file(bucket, key, str(target))
        except ClientError as exc:
            if _error_code(exc) in _MISSING_CODES:
                raise InputError(f"Input object s3://{bucket}/{key} was not found.") from exc
            error = _translate_client_error(exc, f"Failed to download s3://{bucket}/{key}")
            raise error from exc
        except (BotoCoreError, OSError) as exc:
            raise TransientError(f"Failed to download s3://{bucket}/{key}: {exc}") from exc

        if not target.exists() or target.stat().st_size == 0:
            raise InputError(f"Downloaded object s3://{bucket}/{key} is empty.")
        return target

    def exists(self, bucket: str, key: str) -> bool:
        try:
            response = self._client.list_objects_v2(Bucket=bucket, Prefix=key, MaxKeys=1)
            return any(item.get("Key") == key for item in response.get("Contents", []))
        except ClientError as exc:
            if _error_code(exc) in _MISSING_CODES:
                return False
            error = _translate_client_error(exc, f"Failed to check s3://{bucket}/{key}")
            raise error from exc
        except BotoCoreError as exc:
            raise TransientError(f"Failed to check s3://{bucket}/{key}: {exc}") from exc

    def head(self, bucket: str, key: str) -> dict[str, Any]:
        try:
            response = self._client.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            if _error_code(exc) in _MISSING_CODES:
                raise InputError(f"Object s3://{bucket}/{key} was not found.") from exc
            error = _translate_client_error(exc, f"Failed to inspect s3://{bucket}/{key}")
            raise error from exc
        except BotoCoreError as exc:
            raise TransientError(f"Failed to inspect s3://{bucket}/{key}: {exc}") from exc
        return {
            "bytes": int(response.get("ContentLength", 0)),
            "etag": response.get("ETag", "").strip('"'),
        }

    def list_keys(self, bucket: str, prefix: str) -> list[str]:
        keys: list[str] = []
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for item in page.get("Contents", []):
                    keys.append(item["Key"])
        except ClientError as exc:
            error = _translate_client_error(exc, f"Failed to list s3://{bucket}/{prefix}")
            raise error from exc
        except BotoCoreError as exc:
            raise TransientError(f"Failed to list s3://{bucket}/{prefix}: {exc}") from exc
        return keys

    def upload(self, local_path: str | Path, bucket: str, key: str) -> None:
        try:
            self._client.upload_file(
                str(local_path),
                bucket,
                key,
                ExtraArgs={"ContentType": "application/octet-stream"},
            )
        except ClientError as exc:
            error = _translate_client_error(
                exc, f"Failed to upload {local_path} to s3://{bucket}/{key}"
            )
            raise error from exc
        except (BotoCoreError, OSError) as exc:
            raise TransientError(
                f"Failed to upload {local_path} to s3://{bucket}/{key}: {exc}"
            ) from exc

    def copy(self, bucket: str, source_key: str, destination_key: str) -> None:
        try:
            self._client.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": source_key},
                Key=destination_key,
            )
        except ClientError as exc:
            error = _translate_client_error(
                exc,
                f"Failed to copy s3://{bucket}/{source_key} to s3://{bucket}/{destination_key}",
            )
            raise error from exc
        except BotoCoreError as exc:
            raise TransientError(f"Failed to copy s3://{bucket}/{source_key}: {exc}") from exc

    def delete_keys(self, bucket: str, keys: list[str]) -> None:
        if not keys:
            return
        for start in range(0, len(keys), 1000):
            chunk = keys[start : start + 1000]
            try:
                self._client.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True},
                )
            except (ClientError, BotoCoreError) as exc:
                logger.warning("Failed to delete %d staging objects: %s", len(chunk), exc)

    def delete_prefix(self, bucket: str, prefix: str) -> None:
        self.delete_keys(bucket, self.list_keys(bucket, prefix))
