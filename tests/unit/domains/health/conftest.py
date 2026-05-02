"""Shared stub doubles for the health-domain tests.

These doubles satisfy the public health-protocol interfaces without
pulling in a vendor SDK (fhir.resources, pynetdicom, hl7apy, etc.).
Each one is deterministic so the tests assert on exact output shapes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import datetime, timezone
from typing import Any

from pirn.domains.health.protocols.fhir_client import FHIRClient
from pirn.domains.health.protocols.lab_instrument_connection import (
    LabInstrumentConnection,
)
from pirn.domains.health.protocols.omop_connection import OMOPConnection
from pirn.domains.health.protocols.pacs_client import PACSClient
from pirn.domains.health.types.dicom_series import DICOMSeries


class StubFHIRClient(FHIRClient):
    """In-memory FHIR client that records every call."""

    def __init__(self) -> None:
        self.fetched: list[tuple[str, str]] = []
        self.searched: list[tuple[str, Mapping[str, Any]]] = []
        self.closed: int = 0

    async def fetch_resource(
        self, resource_type: str, id: str
    ) -> Mapping[str, Any]:
        self.fetched.append((resource_type, id))
        return {"resourceType": resource_type, "id": id}

    async def search(
        self, resource_type: str, params: Mapping[str, Any]
    ) -> AsyncIterator[Mapping[str, Any]]:
        self.searched.append((resource_type, dict(params)))

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            yield {"resourceType": resource_type, "id": "stub-1"}

        return _aiter()

    async def close(self) -> None:
        self.closed += 1


class StubPACSClient(PACSClient):
    """PACS client that returns a deterministic ``DICOMSeries``."""

    def __init__(self) -> None:
        self.fetched: list[tuple[str, str]] = []
        self.closed: int = 0

    async def fetch_series(
        self, study_uid: str, series_uid: str
    ) -> DICOMSeries:
        self.fetched.append((study_uid, series_uid))
        return DICOMSeries(
            study_uid=study_uid,
            series_uid=series_uid,
            modality="MR",
            num_frames=1,
            fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    async def close(self) -> None:
        self.closed += 1


class StubOMOPConnection(OMOPConnection):
    """OMOP connection with a static concept table."""

    def __init__(self) -> None:
        super().__init__(pool=None)
        self.queried: list[int] = []
        self.closed: int = 0

    async def query_concept(self, concept_id: int) -> Mapping[str, Any]:
        self.queried.append(concept_id)
        return {
            "concept_id": concept_id,
            "concept_name": f"stub-concept-{concept_id}",
            "vocabulary_id": "stub",
        }

    async def close(self) -> None:
        self.closed += 1


class StubLabInstrumentConnection(LabInstrumentConnection):
    """Lab-instrument connection with a deterministic result stream."""

    def __init__(self) -> None:
        self.fetched: list[tuple[str, datetime]] = []
        self.closed: int = 0

    async def fetch_results(
        self, instrument_id: str, since: datetime
    ) -> AsyncIterator[Mapping[str, Any]]:
        self.fetched.append((instrument_id, since))

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            yield {"instrument_id": instrument_id, "result_id": "stub-1"}

        return _aiter()

    async def close(self) -> None:
        self.closed += 1
