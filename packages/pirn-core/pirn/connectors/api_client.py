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

The legacy :meth:`request` method is a generic, string-typed escape
hatch retained for backward compatibility. New code should prefer
vendor methods or capability calls; ``request`` will be deprecated
in a future release once every existing call site has migrated.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Never

from pirn.core.pirn_opaque_value import PirnOpaqueValue

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

        .. deprecated::
            Use vendor-typed methods or
            :mod:`pirn.connectors.capabilities` mixins instead.
            ``request`` is retained as a generic escape hatch for cases
            the typed surface does not yet cover; new code should
            avoid it.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement request()")

    async def close(self) -> None:
        """Close the client and release any underlying resources."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")

    _scrubber: DsnScrubber
    _client: Any
    _closed: bool

    def _import_httpx(self, extra: str, *, quoted: bool = True) -> Any:
        """Import :mod:`httpx` lazily, or raise a uniform install hint.

        The shared, **guard-free** HTTP bootstrap for every ``ApiClient``
        that talks to a vendor over HTTP. It applies no SSRF/egress
        check: these connectors reach operator-configured, frequently
        internal endpoints, and guarding them would break self-hosted
        deployments (settled on PIR-745). Callers that need the module
        object itself (e.g. ``httpx.BasicAuth``) use this directly;
        callers that only build an ``AsyncClient`` use
        :meth:`_build_httpx_client`.

        Args:
            extra: The pip extra that pulls in httpx for this connector,
                used to build the ``pip install pirn[<extra>]`` hint.
            quoted: When ``True`` the install command is wrapped in
                backticks, matching the connectors that already did so.

        Returns:
            The imported ``httpx`` module.

        Raises:
            ImportError: If ``httpx`` is not installed.
        """
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            command = f"pip install pirn[{extra}]"
            hint = f"`{command}`" if quoted else command
            raise ImportError(f"{type(self).__name__} requires httpx; install via {hint}") from exc
        return httpx

    def _build_httpx_client(
        self,
        extra: str,
        *,
        quoted: bool = True,
        scrub_errors: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Build the connector's pooled ``httpx.AsyncClient`` (guard-free).

        Collapses the per-connector ``import httpx`` / construct block
        behind one seam while leaving each connector's own auth, base
        URL, and timeout ``kwargs`` untouched, so the request that goes
        out is identical to the hand-rolled version. No SSRF/egress guard
        is applied (see :meth:`_import_httpx`; PIR-745).

        Args:
            extra: pip extra forwarded to :meth:`_import_httpx`.
            quoted: Install-hint style forwarded to :meth:`_import_httpx`.
            scrub_errors: When ``True`` a construction failure is
                re-raised with credential markers scrubbed via
                :meth:`_reraise_scrubbed`, matching the connectors that
                wrap construction in a scrub; when ``False`` the error
                propagates unchanged.
            **kwargs: Passed straight through to ``httpx.AsyncClient``.

        Returns:
            A new ``httpx.AsyncClient``.
        """
        httpx = self._import_httpx(extra, quoted=quoted)
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
            RuntimeError: If the client has already been closed.
        """
        if self._closed:
            raise RuntimeError(f"{type(self).__name__} is closed")
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
