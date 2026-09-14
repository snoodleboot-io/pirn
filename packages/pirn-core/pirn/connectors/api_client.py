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
   :mod:`pirn.connectors.capabilities` (``TableSource``,
   ``EventEmitter``, ``MetadataCatalog``, ``RecordWriter``,
   ``MetricQuery``). Knots accept capability types — any connector
   that satisfies the capability is interchangeable.

:meth:`request` is the generic, string-typed escape hatch for an
operation the typed surface does not cover. Prefer vendor methods or
capability calls wherever one exists.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Never

from pirn.core.optional_dependency import OptionalDependency
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.exceptions.connector_closed_error import ConnectorClosedError
from pirn.exceptions.connector_config_error import ConnectorConfigError

if TYPE_CHECKING:
    from pirn.connectors.dsn_scrubber import DsnScrubber


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

        The generic escape hatch for an operation the vendor-typed methods
        and :mod:`pirn.connectors.capabilities` mixins do not cover; prefer
        those wherever one exists.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement request()")

    async def close(self) -> None:
        """Close the client and release any underlying resources."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")

    _scrubber: DsnScrubber
    _client: Any
    _closed: bool

    def _build_httpx_client(
        self,
        extra: str,
        *,
        scrub_errors: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Build the connector's pooled ``httpx.AsyncClient`` (guard-free).

        Collapses the per-connector ``import httpx`` / construct block
        behind one seam while leaving each connector's own auth, base
        URL, and timeout ``kwargs`` untouched, so the request that goes
        out is identical to the hand-rolled version. No SSRF/egress guard
        is applied: these connectors reach operator-configured, frequently
        internal endpoints, and guarding them would break self-hosted
        deployments (settled on PIR-745).

        Args:
            extra: The ``pirn-core`` extra named in the install hint when
                ``httpx`` is missing.
            scrub_errors: When ``True`` a construction failure is
                re-raised with credential markers scrubbed via
                :meth:`_reraise_scrubbed`, matching the connectors that
                wrap construction in a scrub; when ``False`` the error
                propagates unchanged.
            **kwargs: Passed straight through to ``httpx.AsyncClient``.

        Returns:
            A new ``httpx.AsyncClient``.

        Raises:
            ImportError: If ``httpx`` is not installed; the message names
                ``pip install "pirn-core[<extra>]"``.
        """
        httpx = OptionalDependency.require("httpx", extra=extra)
        if not scrub_errors:
            return httpx.AsyncClient(**kwargs)
        try:
            return httpx.AsyncClient(**kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)

    async def _ensure_client(self) -> Any:
        """Return the pooled backend client, building it lazily on first use.

        Shared lifecycle for HTTP ``ApiClient``s: raise if the client has
        been closed, otherwise build the vendor client via
        :meth:`_create_client` on first access and pool it for reuse.

        Raises:
            ConnectorClosedError: If the client has already been closed.
        """
        if self._closed:
            raise self._closed_error(type(self).__name__)
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        """Build the concrete backend client (vendor-specific).

        Concrete HTTP connectors override this to construct their own
        ``httpx.AsyncClient`` — typically via :meth:`_build_httpx_client`
        — with the auth, base URL, and timeout the vendor requires.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _create_client()")

    def _reraise_scrubbed(self, exc: BaseException) -> Never:
        """Re-raise ``exc`` with credential markers scrubbed from the message.

        Concrete clients construct ``self._scrubber`` (a
        :class:`pirn.connectors.dsn_scrubber.DsnScrubber`) in their
        ``__init__``. This helper centralises the
        ``raise type(exc)(scrubber.scrub(str(exc))) from None`` pattern so
        every concrete client's connect/auth ``except`` block stays a
        single line.
        """
        raise type(exc)(self._scrubber.scrub(str(exc))) from None

    @staticmethod
    def _closed_error(class_name: str) -> ConnectorClosedError:
        """Build the typed error for "used after close" — call sites ``raise`` it.

        One place for the message so every ``ApiClient`` reports a closed
        client the same way. Mirrors
        :meth:`pirn.connectors.connector_base.ConnectorBase._closed_error`
        for the ``ApiClient`` hierarchy, which does not share ``ConnectorBase``.
        """
        return ConnectorClosedError(f"{class_name} is closed")

    @staticmethod
    def _missing_config_error(class_name: str, resource: str) -> ConnectorConfigError:
        """Build the typed error for "no config and no injected *resource*".

        Mirrors
        :meth:`pirn.connectors.connector_base.ConnectorBase._missing_config_error`
        for the ``ApiClient`` hierarchy.
        """
        return ConnectorConfigError(f"{class_name}: missing config and no injected {resource}")

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
