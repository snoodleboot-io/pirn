`pirn.connectors.object_storage` provides `ObjectStore` implementations for S3, GCS, Azure Blob, HDFS, and local filesystem — it does not execute queries or process file content; use `FileFormat` to encode/decode bytes and `ObjectStoreReadSource`/`ObjectStoreWriteSink` knots to wire stores into a tapestry.

---

## Mental model

Each store has a `*Config` (endpoint, credentials, bucket/container name) and a `*Store` (`ObjectStore` subclass with `read()`, `write()`, `list()`, `delete()`). Create the config, pass it to the store constructor, then pass the store as a config constant to knots. Stores are `PirnOpaqueValue` — create once, reuse across tapestries.

---

## Source map

```
pirn/domains/connectors/object_storage/
├── s3_config.py                  S3Config                — region, bucket, prefix, credentials (key/secret or role)
├── s3_store.py                   S3Store                 — AWS S3 via aiobotocore
├── gcs_config.py                 GcsConfig               — project, bucket, prefix, credentials_json
├── gcs_store.py                  GcsStore                — Google Cloud Storage via gcloud-aio-storage
├── azure_blob_config.py          AzureBlobConfig         — account_name, container, sas_token or connection_string
├── azure_blob_store.py           AzureBlobStore          — Azure Blob Storage via azure-storage-blob async
├── hdfs_config.py                HdfsConfig              — namenode, port, user, krb5_principal
├── hdfs_store.py                 HdfsStore               — HDFS via hdfs3 / libhdfs
├── local_filesystem_config.py    LocalFilesystemConfig   — root_path, create_dirs
└── local_filesystem_store.py     LocalFilesystemStore    — local disk (dev/test only)
```

---

## Canonical pattern

```python
from pirn.connectors.object_storage.s3_config import S3Config
from pirn.connectors.object_storage.s3_store import S3Store
from pirn.connectors.file_formats.parquet_format import ParquetFormat
from pirn.connectors.knots.object_store_read_source import ObjectStoreReadSource
from pirn.connectors.knots.object_store_write_sink import ObjectStoreWriteSink
from pirn import Tapestry, KnotConfig, RunRequest

store = S3Store(config=S3Config(region="us-east-1", bucket="my-bucket"))
fmt   = ParquetFormat()

with Tapestry() as t:
    raw       = ObjectStoreReadSource(store=store, key="input/data.parquet",
                                      file_format=fmt, _config=KnotConfig(id="read"))
    processed = TransformKnot(data=raw, _config=KnotConfig(id="transform"))
    ObjectStoreWriteSink(store=store, key="output/data.parquet",
                         file_format=fmt, data=processed, _config=KnotConfig(id="write"))

result = await t.run(RunRequest())
```

### List keys with a prefix

```python
from pirn.connectors.knots.object_store_list_source import ObjectStoreListSource

with Tapestry() as t:
    keys = ObjectStoreListSource(store=store, prefix="input/", _config=KnotConfig(id="list"))
```

---

## Anti-patterns

**Using `LocalFilesystemStore` in production** — `LocalFilesystemStore` is for local dev and testing only. It does not replicate, has no durability guarantees beyond the OS filesystem, and cannot be shared across distributed workers.

**Passing credentials inline** — inject credentials via environment variables (`AWS_ACCESS_KEY_ID`, `GOOGLE_APPLICATION_CREDENTIALS`, etc.) or IAM roles. Never hardcode secrets in config objects.

---

## Constraints and gotchas

- **Each store requires its own extra:** `pirn[s3]`, `pirn[gcs]`, `pirn[azure-blob]`, `pirn[hdfs]`.
- **`S3Store` uses IAM roles if `access_key` and `secret_key` are absent** — the host must have an instance profile or task role attached.
- **`GcsStore` requires a `credentials_json` path or `GOOGLE_APPLICATION_CREDENTIALS` env var.**
- **`HdfsStore` with Kerberos requires `krb5_principal` and a valid keytab on the executing host.**
- **`ObjectStoreListSource` returns a list of string keys**, not file contents — wire through a `Map` + `ObjectStoreReadSource` to read each one.

---

## Quick reference

| Task | How |
|------|-----|
| Read a file from S3 | `ObjectStoreReadSource(store=S3Store(...), key=..., file_format=...)` |
| Write a file to GCS | `ObjectStoreWriteSink(store=GcsStore(...), key=..., file_format=..., data=...)` |
| List keys under a prefix | `ObjectStoreListSource(store=..., prefix=...)` |
| Delete an object | `store.delete(key)` — call directly outside of a tapestry |
| Local dev store | `LocalFilesystemStore(config=LocalFilesystemConfig(root_path="/tmp/data"))` |

---

*See also: [connectors AGENTIC_USE.md](../AGENTIC_USE.md)*
