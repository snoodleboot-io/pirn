"""Configuration dataclass for :class:`GoogleAnalyticsClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class GoogleAnalyticsConfig(ConnectionConfig):
    """Configuration for a Google Analytics 4 Data API session.

    Attributes
    ----------
    property_id:
        GA4 property identifier (numeric string, e.g. ``"123456789"``).
        Required to scope reporting requests; may be omitted when callers
        embed the property in each request body.
    service_account_json:
        Service-account credentials as a JSON string. When ``None`` the
        Google client falls back to Application Default Credentials
        (``GOOGLE_APPLICATION_CREDENTIALS`` env var, GCE metadata, ...).
    """

    property_id: str | None = None
    service_account_json: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("service_account_json",)
