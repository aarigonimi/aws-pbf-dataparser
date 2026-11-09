from pathlib import Path

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from src.errors import AccessDeniedError, InputError, TransientError
from src.s3_utils import S3Client


def _client_error(code: str, status: int | None = None) -> ClientError:
    response = {"Error": {"Code": code, "Message": code}}
    if status is not None:
        response["ResponseMetadata"] = {"HTTPStatusCode": status}
    return ClientError(response, "TestOperation")


class FakeBotoClient:
    def __init__(self, error: BaseException | None = None):
        self.objects: dict[str, bytes] = {}
        self.error = error
        self.uploaded: list[tuple[str, str]] = []
        self.copied: list[tuple[str, str]] = []
        self.delete_calls: list[list[str]] = []
        self.head_calls: list[tuple[str, str]] = []
        self.list_calls: list[tuple[str, str, int]] = []

    def head_object(self, Bucket, Key):
        self.head_calls.append((Bucket, Key))
        if self.error:
            raise self.error
        if Key not in self.objects:
            raise _client_error("NoSuchKey")
        return {"ContentLength": len(self.objects[Key]), "ETag": '"etag"'}

    def list_objects_v2(self, Bucket, Prefix, MaxKeys):
        self.list_calls.append((Bucket, Prefix, MaxKeys))
        if self.error:
            raise self.error
        keys = [key for key in sorted(self.objects) if key.startswith(Prefix)][:MaxKeys]
        return {"Contents": [{"Key": key} for key in keys]} if keys else {}

    def download_file(self, Bucket, Key, Filename):
        if self.error:
            raise self.error
        if Key not in self.objects:
            raise _client_error("NoSuchKey")
        Path(Filename).write_bytes(self.objects[Key])

    def upload_file(self, Filename, Bucket, Key, ExtraArgs=None):
        if self.error:
            raise self.error
        self.objects[Key] = Path(Filename).read_bytes()
        self.uploaded.append((Bucket, Key))

    def copy_object(self, Bucket, CopySource, Key):
        if self.error:
            raise self.error
        self.objects[Key] = self.objects[CopySource["Key"]]
        self.copied.append((CopySource["Key"], Key))

    def get_paginator(self, name):
        objects = self.objects

        class Paginator:
            def paginate(self, Bucket, Prefix):
                if self_error:
                    raise self_error
                keys = [key for key in sorted(objects) if key.startswith(Prefix)]
                if not keys:
                    return [{}]
                return [{"Contents": [{"Key": key} for key in keys]}]

        self_error = self.error
        return Paginator()

    def delete_objects(self, Bucket, Delete):
        if self.error:
            raise self.error
        keys = [item["Key"] for item in Delete["Objects"]]
        self.delete_calls.append(keys)
        for key in keys:
            self.objects.pop(key, None)


def test_head_and_download_missing_object_are_input_errors(tmp_path: Path):
    client = S3Client(region="us-east-1", client=FakeBotoClient())

    with pytest.raises(InputError):
        client.head("bucket", "missing.pbf")
    with pytest.raises(InputError):
        client.download("bucket", "missing.pbf", tmp_path / "missing.pbf")


def test_head_other_error_is_transient():
    client = S3Client(region="us-east-1", client=FakeBotoClient(error=_client_error("500")))

    with pytest.raises(TransientError):
        client.head("bucket", "key")


def test_exists_returns_false_for_missing_key():
    fake = FakeBotoClient()
    fake.objects["missing.pbf.suffix"] = b"not an exact match"
    client = S3Client(region="us-east-1", client=fake)

    assert client.exists("bucket", "missing.pbf") is False
    assert fake.list_calls == [("bucket", "missing.pbf", 1)]
    assert fake.head_calls == []


def test_head_access_denied_is_non_retryable():
    client = S3Client(region="us-east-1", client=FakeBotoClient(error=_client_error("403")))

    with pytest.raises(AccessDeniedError) as raised:
        client.head("bucket", "key")

    assert raised.value.exit_code == 5


@pytest.mark.parametrize("code", ["SlowDown", "500", "503", "InternalError"])
def test_head_throttling_and_server_errors_are_transient(code: str):
    client = S3Client(region="us-east-1", client=FakeBotoClient(error=_client_error(code)))

    with pytest.raises(TransientError):
        client.head("bucket", "key")


def test_unknown_http_5xx_is_transient():
    client = S3Client(
        region="us-east-1",
        client=FakeBotoClient(error=_client_error("ServiceFailure", status=503)),
    )

    with pytest.raises(TransientError):
        client.head("bucket", "key")


@pytest.mark.parametrize(
    "code",
    ["403", "AccessDenied", "AllAccessDisabled", "InvalidAccessKeyId", "SignatureDoesNotMatch"],
)
@pytest.mark.parametrize("operation", ["download", "head", "exists", "list", "upload", "copy"])
def test_access_denied_is_non_retryable_for_all_s3_operations(
    tmp_path: Path, operation: str, code: str
):
    client = S3Client(region="us-east-1", client=FakeBotoClient(error=_client_error(code)))
    source = tmp_path / "part.parquet"
    source.write_bytes(b"data")

    with pytest.raises(AccessDeniedError) as raised:
        if operation == "download":
            client.download("bucket", "input.pbf", tmp_path / "input.pbf")
        elif operation == "head":
            client.head("bucket", "key")
        elif operation == "exists":
            client.exists("bucket", "key")
        elif operation == "list":
            client.list_keys("bucket", "prefix/")
        elif operation == "upload":
            client.upload(source, "bucket", "staging/part.parquet")
        else:
            client.copy("bucket", "staging/source.parquet", "final/part.parquet")

    assert raised.value.exit_code == 5


@pytest.mark.parametrize("operation", ["download", "head", "exists", "list", "upload", "copy"])
def test_botocore_transport_errors_are_transient(tmp_path: Path, operation: str):
    failure = EndpointConnectionError(endpoint_url="https://s3.example.invalid")
    client = S3Client(region="us-east-1", client=FakeBotoClient(error=failure))
    source = tmp_path / "part.parquet"
    source.write_bytes(b"data")

    with pytest.raises(TransientError):
        if operation == "download":
            client.download("bucket", "input.pbf", tmp_path / "input.pbf")
        elif operation == "head":
            client.head("bucket", "key")
        elif operation == "exists":
            client.exists("bucket", "key")
        elif operation == "list":
            client.list_keys("bucket", "prefix/")
        elif operation == "upload":
            client.upload(source, "bucket", "staging/part.parquet")
        else:
            client.copy("bucket", "staging/source.parquet", "final/part.parquet")


@pytest.mark.parametrize("code", ["SlowDown", "RequestTimeout", "500", "503", "InternalError"])
@pytest.mark.parametrize("operation", ["download", "head", "exists", "list", "upload", "copy"])
def test_throttling_and_server_errors_are_transient_for_all_s3_operations(
    tmp_path: Path, operation: str, code: str
):
    client = S3Client(region="us-east-1", client=FakeBotoClient(error=_client_error(code)))
    source = tmp_path / "part.parquet"
    source.write_bytes(b"data")

    with pytest.raises(TransientError):
        if operation == "download":
            client.download("bucket", "input.pbf", tmp_path / "input.pbf")
        elif operation == "head":
            client.head("bucket", "key")
        elif operation == "exists":
            client.exists("bucket", "key")
        elif operation == "list":
            client.list_keys("bucket", "prefix/")
        elif operation == "upload":
            client.upload(source, "bucket", "staging/part.parquet")
        else:
            client.copy("bucket", "staging/source.parquet", "final/part.parquet")


def test_download_writes_file_and_rejects_empty(tmp_path: Path):
    fake = FakeBotoClient()
    fake.objects["input.pbf"] = b"abc"
    client = S3Client(region="us-east-1", client=fake)

    target = client.download("bucket", "input.pbf", tmp_path / "input.pbf")
    assert target.read_bytes() == b"abc"

    fake.objects["empty.pbf"] = b""
    with pytest.raises(InputError):
        client.download("bucket", "empty.pbf", tmp_path / "empty.pbf")


def test_upload_copy_and_list(tmp_path: Path):
    fake = FakeBotoClient()
    client = S3Client(region="us-east-1", client=fake)
    source = tmp_path / "part.parquet"
    source.write_bytes(b"parquet")

    client.upload(source, "bucket", "staging/part.parquet")
    client.copy("bucket", "staging/part.parquet", "final/part.parquet")

    assert fake.uploaded == [("bucket", "staging/part.parquet")]
    assert fake.copied == [("staging/part.parquet", "final/part.parquet")]
    assert client.list_keys("bucket", "final/") == ["final/part.parquet"]


def test_delete_keys_chunks_and_swallows_failures():
    fake = FakeBotoClient()
    fake.objects = {f"k/{index}": b"x" for index in range(1001)}
    client = S3Client(region="us-east-1", client=fake)

    client.delete_keys("bucket", list(fake.objects))

    assert len(fake.delete_calls) == 2
    assert fake.objects == {}

    failing = S3Client(region="us-east-1", client=FakeBotoClient(error=_client_error("500")))
    failing.delete_keys("bucket", ["a"])
