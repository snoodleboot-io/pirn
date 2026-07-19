"""Shared stub doubles for the health-domain tests.

These doubles satisfy the public health-protocol interfaces without
pulling in a vendor SDK (fhir.resources, pynetdicom, hl7apy, etc.).
Each one is deterministic so the tests assert on exact output shapes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pirn_health.health_llm_provider import HealthLLMProvider
from pirn_health.protocols.fhir_client import FHIRClient
from pirn_health.protocols.lab_instrument_connection import (
    LabInstrumentConnection,
)
from pirn_health.protocols.omop_connection import OMOPConnection
from pirn_health.protocols.pacs_client import PACSClient
from pirn_health.types.dicom_series import DICOMSeries


class StubLLMProvider(HealthLLMProvider):
    """Scripted :class:`HealthLLMProvider` double for clinical-NLP tests.

    Local to the health package so its tests stay isolated from
    ``pirn-agents`` (``HealthLLMProvider`` is health's own domain-owned
    interface, PIR-735 — no cross-domain dependency).
    """

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[list[Mapping[str, Any]]] = []

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        self.calls.append([dict(m) for m in messages])
        if self._index < len(self._responses):
            text = self._responses[self._index]
            self._index += 1
        else:
            text = self._responses[-1] if self._responses else ""
        return {"role": "assistant", "content": text}

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        chunks = self._responses or [""]

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for chunk in chunks:
                yield {"content": chunk}

        return _aiter()

    async def close(self) -> None:
        return None


class StubFHIRClient(FHIRClient):
    """In-memory FHIR client that records every call."""

    def __init__(self) -> None:
        self.fetched: list[tuple[str, str]] = []
        self.searched: list[tuple[str, Mapping[str, Any]]] = []
        self.closed: int = 0

    async def fetch_resource(self, resource_type: str, id: str) -> Mapping[str, Any]:
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

    async def fetch_series(self, study_uid: str, series_uid: str) -> DICOMSeries:
        self.fetched.append((study_uid, series_uid))
        return DICOMSeries(
            study_uid=study_uid,
            series_uid=series_uid,
            modality="MR",
            num_frames=1,
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
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
