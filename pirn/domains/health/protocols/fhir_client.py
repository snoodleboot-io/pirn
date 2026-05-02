"""Interface for asynchronous FHIR-server clients.

Concrete implementations wrap a vendor SDK (``fhir.resources``,
``fhirclient``, raw ``httpx``); knots depend only on this interface so
the production stack and stub doubles remain interchangeable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class FHIRClient(PirnOpaqueValue):
    """Interface every FHIR-server client must satisfy."""

    async def fetch_resource(
        self, resource_type: str, id: str
    ) -> Mapping[str, Any]:
        """Return a single FHIR resource by ``resource_type`` / ``id``."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement fetch_resource()"
        )

    async def search(
        self, resource_type: str, params: Mapping[str, Any]
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Yield matching FHIR resources for ``resource_type`` + ``params``."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement search()"
        )

    async def close(self) -> None:
        """Release any underlying transport resources."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement close()"
        )

    def _clear_credentials(self) -> None:
        """Drop the in-memory credential reference held by the client.

        Concrete implementations should call this from ``close()`` after
        tearing down the live SDK / client. It nulls ``self._config`` so
        the credential string (token, api key, secret) becomes garbage-
        collectable as soon as the caller drops the client reference.
        Long-running processes that hold client references after
        ``close()`` benefit; default deployments are unaffected.
        """
        self._config = None
