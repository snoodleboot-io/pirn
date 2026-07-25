"""``ConnectorBase`` — base class for connectors holding a pooled backend client.

A connector wraps live client state (an HTTP session, a vector-store client, a
database pool) and is therefore opaque at the pirn IO boundary. Concrete
connectors override :meth:`_create_client` to lazily build their backend client
via :meth:`_require` (so importing this module never imports any backend), and
the base provides deterministic, idempotent lifecycle management:

    * construct-once-reuse via :meth:`_get_client` (the pooling lever),
    * deterministic teardown via :meth:`close`,
    * credential scrubbing via :meth:`_clear_credentials`.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, ClassVar

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.security.credential_ref import CredentialRef


class ConnectorBase(PirnOpaqueValue):
    """Base class for connectors that hold a lazily-pooled backend client."""

    #: Distribution whose extras provide this connector's optional backends. It is
    #: named in the friendly ``ImportError`` raised by :meth:`_require`. Connectors
    #: shipped in another distribution override it (e.g. pirn-agents connectors set
    #: ``_install_dist = "pirn-agents"``) so the install hint points at the right
    #: package.
    _install_dist: ClassVar[str] = "pirn-core"

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

    def _require(self, extra: str, module: str) -> ModuleType:
        """Import ``module`` lazily, raising a friendly error if it is missing.

        Turns a missing optional backend into an ``ImportError`` naming the exact
        ``pip install`` command — using :attr:`_install_dist` so the hint points at
        the distribution that ships this connector.

        Raises:
            ImportError: If ``module`` cannot be imported.
        """
        try:
            return importlib.import_module(module)
        except ImportError as exc:
            raise ImportError(
                f"{module!r} is required for this feature; install it with: "
                f'pip install "{self._install_dist}[{extra}]"'
            ) from exc

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

        Implementations use :meth:`_require` to lazily import their backend.

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

    def _pirn_audit_dict(self) -> Any:
        """Return a stable, secret-free audit form.

        The live client is opaque and the raw secret never appears; only the
        connector type and whether a credential is currently held are emitted.
        """
        return {
            "connector": type(self).__name__,
            "has_credential": self._credential is not None,
        }
