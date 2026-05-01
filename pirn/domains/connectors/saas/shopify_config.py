"""Configuration dataclass for :class:`ShopifyClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class ShopifyConfig(ConnectionConfig):
    """Configuration for a Shopify Admin REST/GraphQL session.

    Attributes
    ----------
    shop_url:
        Fully-qualified store domain, e.g. ``my-store.myshopify.com``.
    access_token:
        Admin API access token (``shpat_...``).
    api_version:
        Pinned Admin API version (default ``2024-04``).
    """

    shop_url: str | None = None
    access_token: str | None = None
    api_version: str = "2024-04"

    sensitive_fields: ClassVar[tuple[str, ...]] = ("access_token",)
