"""Configuration dataclass for :class:`BigqueryPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class BigqueryConfig(ConnectionConfig):
    """Configuration for a Google BigQuery client.

    Attributes
    ----------
    project_id:
        GCP project hosting the BigQuery dataset.
    dataset_id:
        Optional default dataset for unqualified table references.
    credentials_path:
        Optional path to a service-account JSON key file. When ``None``,
        ``google-cloud-bigquery`` falls back to Application Default
        Credentials.
    location:
        BigQuery location/region used for jobs (default ``"US"``).
    """

    project_id: str | None = None
    dataset_id: str | None = None
    credentials_path: str | None = None
    location: str = "US"

    sensitive_fields: ClassVar[tuple[str, ...]] = ("credentials_path",)
