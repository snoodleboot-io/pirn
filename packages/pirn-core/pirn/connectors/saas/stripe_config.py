"""Configuration dataclass for :class:`StripeClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class StripeConfig(ConnectionConfig):
    """Configuration for a Stripe API session.

    Attributes
    ----------
    api_key:
        Stripe secret key (``sk_live_...`` or ``sk_test_...``).
    api_version:
        Pinned API version (``2024-09-30.acacia`` etc.). When ``None``,
        the SDK default is used.
    """

    api_key: str | None = None
    api_version: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("api_key",)
