"""``DICOMIngestor`` — pull a DICOM series from PACS.

Production version uses ``pydicom`` / ``dicomweb-client`` over WADO-RS.
This stub validates inputs and proxies through the injected
:class:`PACSClient` so PACS doubles work in unit tests.

Algorithm:
    1. Receive client PACSClient, study_uid, and series_uid strings.
    2. Validate client is a PACSClient and both UIDs are non-empty strings.
    3. Delegate to client.fetch_series(study_uid, series_uid).
    4. Return the resulting DICOMSeries.


References:
    - DICOMweb: https://www.dicomstandard.org/dicomweb
    - pydicom: https://pydicom.github.io/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.protocols.pacs_client import PACSClient
from pirn.domains.health.types.dicom_series import DICOMSeries


class DICOMIngestor(Knot):
    """Fetch a DICOM series from PACS."""

    def __init__(
        self,
        *,
        client: Knot | PACSClient,
        study_uid: Knot | str,
        series_uid: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            client=client,
            study_uid=study_uid,
            series_uid=series_uid,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        client: PACSClient,
        study_uid: str,
        series_uid: str,
        **_: Any,
    ) -> DICOMSeries:
        """Fetch the configured study/series from PACS and return a DICOMSeries.

        Args:
            client: PACSClient instance to use for the DICOM retrieval.
            study_uid: Non-empty DICOM study UID string.
            series_uid: Non-empty DICOM series UID string.

        Returns:
            DICOMSeries carrying the study and series UIDs retrieved from PACS.

        Raises:
            TypeError: If client is not a PACSClient or UIDs are not strings.
            ValueError: If any UID is empty.
        """
        if not isinstance(client, PACSClient):
            raise TypeError("DICOMIngestor: client must be a PACSClient")
        for label, value in (
            ("study_uid", study_uid),
            ("series_uid", series_uid),
        ):
            if not isinstance(value, str):
                raise TypeError(f"DICOMIngestor: {label} must be a string")
            if not value:
                raise ValueError(f"DICOMIngestor: {label} must be non-empty")
        return await client.fetch_series(study_uid, series_uid)
