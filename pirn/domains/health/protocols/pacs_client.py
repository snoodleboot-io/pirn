"""Interface for asynchronous PACS / DICOMweb clients.

Concrete implementations talk to PACS over DICOMweb (QIDO/WADO) or via
``pynetdicom``; knots see only :class:`PACSClient` so the production
stack and stub doubles remain interchangeable.
"""

from __future__ import annotations

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.health.types.dicom_series import DICOMSeries


class PACSClient(PirnOpaqueValue):
    """Interface every PACS/DICOMweb client must satisfy."""

    async def fetch_series(
        self, study_uid: str, series_uid: str
    ) -> DICOMSeries:
        """Fetch and return the DICOM series identified by the UIDs."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement fetch_series()"
        )

    async def close(self) -> None:
        """Release any underlying transport resources."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement close()"
        )
