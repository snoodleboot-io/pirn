"""Configuration dataclass for :class:`ZendeskClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class ZendeskConfig(ConnectionConfig):
    """Configuration for a Zendesk Support API session.

    Attributes
    ----------
    subdomain:
        Zendesk account subdomain (e.g. ``acme`` for
        ``acme.zendesk.com``).
    email:
        Agent or admin email address used as the API username.
    api_token:
        API token used together with ``email`` (token auth).
    oauth_token:
        OAuth bearer token, used in place of email + api_token.
    """

    subdomain: str | None = None
    email: str | None = None
    api_token: str | None = None
    oauth_token: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("api_token", "oauth_token")
