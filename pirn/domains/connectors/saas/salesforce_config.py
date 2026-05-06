"""Configuration dataclass for :class:`SalesforceClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class SalesforceConfig(ConnectionConfig):
    """Configuration for a Salesforce REST/SOAP/Bulk session.

    Attributes
    ----------
    username / password / security_token:
        Username-password flow credentials.
    domain:
        ``login`` (production) or ``test`` (sandbox), or a custom My Domain.
    consumer_key / consumer_secret:
        Connected-app OAuth credentials, used by the JWT/OAuth flows.
    """

    username: str | None = None
    password: str | None = None
    security_token: str | None = None
    domain: str = "login"
    consumer_key: str | None = None
    consumer_secret: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = (
        "password",
        "security_token",
        "consumer_secret",
    )
