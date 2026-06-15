"""Interface for asynchronous PACS / DICOMweb clients.

Concrete implementations talk to PACS over DICOMweb (QIDO/WADO) or via
``pynetdicom``; knots see only :class:`PACSClient` so the production
stack and stub doubles remain interchangeable.
"""

from __future__ import annotations

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_health.types.dicom_series import DICOMSeries


class PACSClient(PirnOpaqueValue):
    """Interface every PACS/DICOMweb client must satisfy."""

    async def fetch_series(self, study_uid: str, series_uid: str) -> DICOMSeries:
        """Fetch and return the DICOM series identified by the UIDs."""
        raise NotImplementedError(f"{type(self).__name__} must implement fetch_series()")

    async def close(self) -> None:
        """Release any underlying transport resources."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")

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
