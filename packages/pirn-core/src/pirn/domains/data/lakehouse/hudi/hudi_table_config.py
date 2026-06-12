"""Configuration dataclass for :class:`HudiTable`.

Hudi's Python ecosystem is thinner than Delta's or Iceberg's: native
write support is currently provided through Spark/Java, with Python
limited to read-only access. The config carries the table path and the
write-side metadata (record key, precombine field, partition column)
that a future Python writer or a Spark-backed writer would consume.
"""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class HudiTableConfig(ConnectionConfig):
    """Configuration for a Hudi table.

    Attributes
    ----------
    table_path:
        Filesystem or object-store URI of the Hudi table root.
    table_type:
        Hudi storage layout — ``"COPY_ON_WRITE"`` (default) or
        ``"MERGE_ON_READ"``.
    record_key_field:
        Column whose value uniquely identifies a record.
    precombine_field:
        Column used to break ties between two writes for the same
        record key (typically a monotonic timestamp).
    partition_path_field:
        Optional column used to derive the partition path; ``None`` for
        a non-partitioned table.
    """

    table_path: str | None = None
    table_type: str = "COPY_ON_WRITE"
    record_key_field: str = "id"
    precombine_field: str = "ts"
    partition_path_field: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
