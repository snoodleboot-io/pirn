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

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class ApiClient:
    """Interface every SaaS connector must satisfy."""

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

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Tell pydantic to treat clients as opaque.

        Concrete clients wrap vendor SDKs (Salesforce, GitHub, Stripe,
        ...) that are not pydantic-compatible. Pirn IO validation just
        needs ``isinstance(value, ApiClient)``; this short-circuit
        avoids pydantic descending into vendor internals.

        A dedicated serialiser emits a stable identity-based string
        token so pirn's content-addressing cache can serialise the
        client without introducing spurious cache hits across truly
        different clients.
        """
        return core_schema.is_instance_schema(
            cls,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: f"<{type(v).__name__}@{id(v):x}>",
                when_used="always",
            ),
        )
