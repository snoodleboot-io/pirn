"""Interface for async HTTP-based SaaS API connectors.

Concrete implementations (Salesforce, HubSpot, Stripe, GitHub, ...)
inherit from :class:`ApiClient` and override every method. Following
the existing pirn interface convention (see
:class:`DatabaseConnectionPool`, :class:`MessageBroker`,
:class:`ObjectStore`) — base methods raise :class:`NotImplementedError`
naming the concrete subclass that failed to implement them.

Pagination is intentionally NOT part of the interface — every SaaS API
uses a different pagination shape (cursor, offset, page-token, Link
header, nextRecordsUrl, ...). Concrete connectors expose their own
pagination helpers on top of :meth:`request`.
"""

from __future__ import annotations

from typing import Any, Mapping

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
        """Send an authenticated HTTP request and return the parsed body."""
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

