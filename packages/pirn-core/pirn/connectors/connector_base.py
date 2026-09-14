"""``ConnectorBase`` — base class for connectors holding a pooled backend client.

A connector wraps live client state (an HTTP session, a vector-store client, a
database pool) and is therefore opaque at the pirn IO boundary. Concrete
connectors override :meth:`_create_client` to lazily build their backend client
via :meth:`pirn.core.optional_dependency.OptionalDependency.require` (so
importing this module never imports any backend), and
the base provides deterministic, idempotent lifecycle management:

    * construct-once-reuse via :meth:`_get_client` (the pooling lever),
    * deterministic teardown via :meth:`close`,
    * credential scrubbing via :meth:`_clear_credentials`.
"""

from __future__ import annotations

from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.exceptions.connector_closed_error import ConnectorClosedError
from pirn.exceptions.connector_config_error import ConnectorConfigError
from pirn.security.credential_ref import CredentialRef


class ConnectorBase(PirnOpaqueValue):
    """Base class for connectors that hold a lazily-pooled backend client."""

    def __init__(self, *, credential: CredentialRef | None = None) -> None:
        """Initialise the connector.

        Args:
            credential: Optional :class:`CredentialRef` used to authenticate the
                backend client. Must be a ``CredentialRef`` or ``None``.

        Raises:
            TypeError: If ``credential`` is neither a ``CredentialRef`` nor
                ``None``.
        """
        if credential is not None and not isinstance(credential, CredentialRef):
            raise TypeError(
                f"credential must be a CredentialRef or None, got {type(credential).__name__}"
            )
        self._credential: CredentialRef | None = credential
        self._client: Any | None = None

    async def _get_client(self) -> Any:
        """Return the pooled client, constructing it once and caching it.

        The client is built lazily on first call via :meth:`_create_client`;
        subsequent calls return the cached instance (construct-once-reuse is the
        pooling lever).
        """
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        """Build and return the backend client. Overridden by concrete connectors.

        Implementations use :meth:`OptionalDependency.require
        <pirn.core.optional_dependency.OptionalDependency.require>` to lazily
        import their backend.

        Raises:
            NotImplementedError: Always, in the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _create_client()")

    async def close(self) -> None:
        """Release the pooled client deterministically and idempotently.

        If a client is held, its async ``aclose`` is awaited when present, else
        its sync ``close`` is called; the client reference is then dropped and
        credentials are scrubbed. Calling ``close`` again is a safe no-op.
        """
        client: Any = self._client
        if client is not None:
            if callable(getattr(client, "aclose", None)):
                await client.aclose()
            elif callable(getattr(client, "close", None)):
                client.close()
            self._client = None
        self._clear_credentials()

    def _clear_credentials(self) -> None:
        """Drop the credential reference so the secret becomes GC-able."""
        self._credential = None

    @staticmethod
    def _closed_error(class_name: str) -> ConnectorClosedError:
        """Build the typed error for "used after close" — call sites ``raise`` it.

        One place for the message so every connector reports a closed
        client the same way. Returns rather than raises so a call site
        keeps its own ``raise`` statement, which is what a type checker and
        a reader both expect at the point control actually leaves the
        function.
        """
        return ConnectorClosedError(f"{class_name} is closed")

    @staticmethod
    def _missing_config_error(class_name: str, resource: str) -> ConnectorConfigError:
        """Build the typed error for "no config and no injected *resource*".

        *resource* names the backend object the connector needed and had
        neither a config to build nor an injected instance of (e.g.
        ``"client"``, ``"pool"``, ``"driver"``).
        """
        return ConnectorConfigError(f"{class_name}: missing config and no injected {resource}")

    def __pirn_canonical__(self) -> Any:
        """Return the content-hash form: an identity-keyed token by default.

        :meth:`_pirn_audit_dict` is a per-class constant, so it cannot be the
        hash. Two connectors of one class aimed at different endpoints, models
        or databases would hash equal, and replay would serve a recording made
        against one to a run configured with the other (PIR-848). Keying on
        identity turns that false match into a false mismatch, which is safe:
        replay refuses instead of substituting.

        The token is the one :class:`PirnOpaqueValue` emits by default,
        ``<TypeName@identity_token>``. It is unique per instance even when
        CPython reuses a freed connector's address (PIR-852). It holds no
        configuration, so no credential can reach lineage through it, and it
        does not change when :meth:`_clear_credentials` runs. A copy of a
        connector is a different instance and gets a different token.

        A subclass whose behaviour is fully determined by secret-free
        configuration may override this to return that configuration instead.

        Known gap (PIR-853): a connector nested inside a pydantic model is still
        hashed through ``model_dump``, i.e. through :meth:`_pirn_audit_dict`, so
        this hook is not reached there.
        """
        return PirnOpaqueValue._pirn_audit_dict(self)

    def _pirn_audit_dict(self) -> Any:
        """Return a stable, secret-free audit form.

        The live client is opaque and the raw secret never appears; only the
        connector type and whether a credential is currently held are emitted.
        This is an audit form, not an identity: content hashing goes through
        :meth:`__pirn_canonical__`.
        """
        return {
            "connector": type(self).__name__,
            "has_credential": self._credential is not None,
        }
