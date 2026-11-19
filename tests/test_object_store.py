import io

import pytest

from backend import object_store
from backend.object_store import LocalObjectStore, ObjectStoreError, S3ObjectStore


def test_local_object_store_uses_opaque_keys(tmp_path):
    store = LocalObjectStore(tmp_path)
    key = "a" * 32

    store.put(key, b"encrypted")

    assert store.get(key) == b"encrypted"
    assert list(tmp_path.rglob("*.bin"))[0].name == f"{key}.bin"
    store.delete(key)
    with pytest.raises(ObjectStoreError, match="object_not_found"):
        store.get(key)


def test_s3_store_writes_private_opaque_objects(monkeypatch):
    calls = []

    class Client:
        def put_object(self, **kwargs):
            calls.append(("put", kwargs))

        def get_object(self, **kwargs):
            calls.append(("get", kwargs))
            return {"Body": io.BytesIO(b"encrypted")}

        def delete_object(self, **kwargs):
            calls.append(("delete", kwargs))

    class Boto:
        @staticmethod
        def client(_service, **_options):
            return Client()

    monkeypatch.setattr(object_store, "boto3", Boto())
    store = S3ObjectStore("private-bucket", prefix="receipts")
    key = "b" * 32

    store.put(key, b"encrypted")
    assert store.get(key) == b"encrypted"
    store.delete(key)

    assert calls[0][1]["Bucket"] == "private-bucket"
    assert calls[0][1]["Key"] == f"receipts/{key[:2]}/{key}.bin"
    assert "ACL" not in calls[0][1]
    assert [name for name, _ in calls] == ["put", "get", "delete"]
