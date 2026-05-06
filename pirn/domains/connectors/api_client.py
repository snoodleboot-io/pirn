"""Interface for async HTTP-based SaaS API connectors.

Concrete implementations (Salesforce, HubSpot, Stripe, GitHub, ...)
inherit from :class:`ApiClient` for lifecycle management
(``close()``) and credential-safe error reporting
(``_reraise_scrubbed``). The preferred way to interact with a
connector is via:

1. **Vendor-typed methods.** Each connector exposes domain-specific
   methods (``StripeClient.list_charges``, ``GitHubClient.get_repo``,
   ``SalesforceClient.soql``).
2. **Capability mixins** in
   :mod:`pirn.domains.connectors.capabilities` (``TableSource``,
   ``EventEmitter``, ``MetadataCatalog``, ``RecordWriter``,
   ``MetricQuery``). Knots accept capability types — any connector
   that satisfies the capability is interchangeable.

The legacy :meth:`request` method is a generic, string-typed escape
hatch retained for backward compatibility. New code should prefer
vendor methods or capability calls; ``request`` will be deprecated
in a future release once every existing call site has migrated.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class ApiClient(PirnOpaqueValue):
    """Interface every SaaS connector must satisfy.

    Pydantic treats clients as opaque (see
    :class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
    identity-keyed serialiser keeps content-addressing cache stable
    without descending into vendor SDKs (Salesforce, GitHub, Stripe,
    ...).
    """

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Send an authenticated HTTP request and return the parsed body.

        .. deprecated::
            Use vendor-typed methods or
            :mod:`pirn.domains.connectors.capabilities` mixins instead.
            ``request`` is retained as a generic escape hatch for cases
            the typed surface does not yet cover; new code should
            avoid it.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement request()"
        )

    async def close(self) -> None:
        """Close the client and release any underlying resources."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement close()"
        )

    def _reraise_scrubbed(self, exc: BaseException) -> None:
        """Re-raise ``exc`` with credential markers scrubbed from the message.

        Concrete clients construct ``self._scrubber`` (a
        :class:`pirn.domains.connectors.dsn_scrubber.DsnScrubber`) in their
        ``__init__``. This helper centralises the
        ``raise type(exc)(scrubber.scrub(str(exc))) from None`` pattern so
        every concrete client's connect/auth ``except`` block stays a
        single line.
        """
        raise type(exc)(self._scrubber.scrub(str(exc))) from None

    def _clear_credentials(self) -> None:
        """Drop the in-memory credential reference held by the client.

        Concrete clients should call this from ``close()`` after tearing
        down the live SDK / httpx client. It nulls ``self._config`` so
        the credential string (token, api key, secret) becomes garbage-
        collectable as soon as the caller drops the client reference.
        Long-running processes that hold client references after
        ``close()`` benefit; default deployments are unaffected.
        """
        self._config = None

