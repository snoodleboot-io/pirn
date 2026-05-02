"""Configuration dataclass for :class:`IcebergTable`.

Identifies an Iceberg table through a (catalog, identifier) pair where
``catalog_properties`` carries the catalog connection details (REST
URL, Glue region, Hive metastore URI, S3 / object-store credentials,
…). Catalog properties may contain individual secret values; redaction
of those keys is the caller's responsibility on logging boundaries —
the field itself is a structured mapping rather than a single secret
string.
"""

from __future__ import annotations

from dataclasses import field
from typing import ClassVar, Mapping

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class IcebergTableConfig(ConnectionConfig):
    """Configuration for an Iceberg table.

    Attributes
    ----------
    catalog_name:
        Name passed to ``pyiceberg.catalog.load_catalog`` to select the
        catalog entry from local config (``~/.pyiceberg.yaml``) or to
        identify a programmatically-loaded catalog.
    catalog_properties:
        Properties forwarded to the catalog loader (URI, warehouse,
        credentials, region, …). Keys vary by catalog backend.
    table_identifier:
        Fully qualified table name, e.g. ``"namespace.table"``.
    namespace:
        Optional explicit namespace; usually unnecessary when
        ``table_identifier`` is fully qualified.
    """

    catalog_name: str | None = None
    catalog_properties: Mapping[str, str] = field(default_factory=dict)
    table_identifier: str | None = None
    namespace: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
