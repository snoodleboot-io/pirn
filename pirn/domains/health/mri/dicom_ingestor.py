"""``DICOMIngestor`` — pull a DICOM series from PACS.

Production version uses ``pydicom`` / ``dicomweb-client`` over WADO-RS.
Fetches the series metadata via the injected :class:`PACSClient` and bundles
it with the caller-supplied staging directory into a :class:`DICOMPayload`
so downstream knots (e.g. NIfTIConverter) receive both the lineage metadata
and a filesystem path in one input.

Algorithm:
    1. Receive client PACSClient, study_uid, series_uid, and staging_dir strings.
    2. Validate client is a PACSClient, both UIDs are non-empty strings, and staging_dir is non-empty.
    3. Delegate to client.fetch_series(study_uid, series_uid).
    4. Return DICOMPayload(series=result, dicom_dir=staging_dir).


References:
    - DICOMweb: https://www.dicomstandard.org/dicomweb
    - pydicom: https://pydicom.github.io/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.protocols.pacs_client import PACSClient
from pirn.domains.health.types.dicom_payload import DICOMPayload


class DICOMIngestor(Knot):
    """Fetch a DICOM series from PACS and return a :class:`DICOMPayload`."""

    def __init__(
        self,
        *,
        client: Knot | PACSClient,
        study_uid: Knot | str,
        series_uid: Knot | str,
        staging_dir: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            client=client,
            study_uid=study_uid,
            series_uid=series_uid,
            staging_dir=staging_dir,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        client: PACSClient,
        study_uid: str,
        series_uid: str,
        staging_dir: str,
        **_: Any,
    ) -> DICOMPayload:
        """Fetch the configured study/series from PACS and return a DICOMPayload.

        Args:
            client: PACSClient instance to use for the DICOM retrieval.
            study_uid: Non-empty DICOM study UID string.
            series_uid: Non-empty DICOM series UID string.
            staging_dir: Non-empty local directory path where DICOM files are staged.

        Returns:
            DICOMPayload carrying the DICOMSeries metadata and the staging directory path.

        Raises:
            TypeError: If client is not a PACSClient or UIDs are not strings.
            ValueError: If any UID or staging_dir is empty.
        """
        if not isinstance(client, PACSClient):
            raise TypeError("DICOMIngestor: client must be a PACSClient")
        for label, value in (
            ("study_uid", study_uid),
            ("series_uid", series_uid),
            ("staging_dir", staging_dir),
        ):
            if not isinstance(value, str):
                raise TypeError(f"DICOMIngestor: {label} must be a string")
            if not value:
                raise ValueError(f"DICOMIngestor: {label} must be non-empty")
        series = await client.fetch_series(study_uid, series_uid)
        return DICOMPayload(series=series, dicom_dir=staging_dir)
