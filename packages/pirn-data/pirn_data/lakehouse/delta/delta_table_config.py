"""Configuration dataclass for :class:`DeltaTable`.

Wraps a Delta Lake table location and any storage backend options
(S3 credentials, ABFS account keys, GCS service-account JSON, …) that
``deltalake`` forwards to its object-store layer.

The ``storage_options`` mapping may contain individual secret values
(e.g. ``"aws_secret_access_key"``); the redacting :meth:`__repr__`
inherited from :class:`ConnectionConfig` handles the dict-key heuristic
on a per-key basis when the caller passes the dict through normal
logging paths. The field itself is not flagged as a single secret string
because it is a structured mapping.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import field
from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class DeltaTableConfig(ConnectionConfig):
    """Configuration for a Delta Lake table.

    Attributes
    ----------
    table_uri:
        Filesystem or object-store URI of the Delta table root
        (e.g. ``"s3://bucket/db/table"``, ``"file:///data/tbl"``).
    storage_options:
        Backend-specific key/value pairs forwarded to ``deltalake`` for
        authentication and tuning. May contain secrets — caller is
        responsible for redaction at log boundaries.
    """

    table_uri: str | None = None
    storage_options: Mapping[str, str] = field(default_factory=dict)

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
