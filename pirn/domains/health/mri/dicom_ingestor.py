"""``DICOMIngestor`` — pull a DICOM series from PACS.

Production version uses ``pydicom`` / ``dicomweb-client`` over WADO-RS.
This stub validates inputs and proxies through the injected
:class:`PACSClient` so PACS doubles work in unit tests.
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
        client: PACSClient,
        study_uid: str,
        series_uid: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._client = client
        self._study_uid = study_uid
        self._series_uid = series_uid
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DICOMSeries:
        return await self._client.fetch_series(
            self._study_uid, self._series_uid
        )
