"""Shared stub doubles and deterministic fixtures for oil-and-gas domain tests.

The stubs satisfy the public protocol interfaces (``HistorianConnection``,
``SeismicVolumeStore``, ``WellDataService``) without pulling in any
vendor SDK. The fixtures provide ready-made instances of the common
frozen dataclass types so the per-knot tests can stay focused on
process behaviour.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime

import pytest

from pirn.domains.oilgas.protocols.historian_connection import HistorianConnection
from pirn.domains.oilgas.protocols.seismic_volume_store import SeismicVolumeStore
from pirn.domains.oilgas.protocols.well_data_service import WellDataService
from pirn.domains.oilgas.types.deviation_survey import DeviationSurvey
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.types.pvt_table import PVTTable
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class StubHistorianConnection(HistorianConnection):
    """Deterministic in-memory historian double."""

    def __init__(self) -> None:
        self.fetched: list[tuple[str, datetime]] = []
        self.closed: bool = False

    async def fetch_tag(
        self, tag: str, since: datetime
    ) -> AsyncIterator[Mapping[str, object]]:
        self.fetched.append((tag, since))

        async def _aiter() -> AsyncIterator[Mapping[str, object]]:
            yield {"timestamp": since, "value": 1.0}

        return _aiter()

    async def close(self) -> None:
        self.closed = True


class StubSeismicVolumeStore(SeismicVolumeStore):
    """Deterministic in-memory seismic-volume-store double."""

    def __init__(self) -> None:
        self.requested: list[str] = []
        self.closed: bool = False

    async def fetch_volume(self, volume_id: str) -> SegyVolume:
        self.requested.append(volume_id)
        return SegyVolume(volume_id=volume_id)

    async def close(self) -> None:
        self.closed = True


class StubWellDataService(WellDataService):
    """Deterministic in-memory well-data-service double."""

    def __init__(self) -> None:
        self.fetched_wells: list[str] = []
        self.listed_fields: list[str] = []
        self.closed: bool = False

    async def fetch_well(self, well_id: str) -> Mapping[str, object]:
        self.fetched_wells.append(well_id)
        return {"well_id": well_id, "name": f"well-{well_id}"}

    async def list_wells(self, field_id: str) -> AsyncIterator[str]:
        self.listed_fields.append(field_id)

        async def _aiter() -> AsyncIterator[str]:
            yield f"{field_id}-well-1"

        return _aiter()

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def stub_historian() -> StubHistorianConnection:
    return StubHistorianConnection()


@pytest.fixture
def stub_seismic_store() -> StubSeismicVolumeStore:
    return StubSeismicVolumeStore()


@pytest.fixture
def stub_well_service() -> StubWellDataService:
    return StubWellDataService()


@pytest.fixture
def sample_segy_volume() -> SegyVolume:
    return SegyVolume(
        volume_id="vol-1",
        inline_count=100,
        xline_count=200,
        sample_count=300,
    )


@pytest.fixture
def sample_las_file() -> LASFile:
    return LASFile(
        well_id="well-A",
        curves=("GR", "RHOB", "NPHI", "RT"),
        depth_unit="m",
    )


@pytest.fixture
def sample_deviation_survey() -> DeviationSurvey:
    return DeviationSurvey(well_id="well-A", station_count=42)


@pytest.fixture
def sample_pvt_table() -> PVTTable:
    return PVTTable(fluid_id="fluid-A", pressure_count=10, temperature_count=5)


@pytest.fixture
def sample_scada_series() -> ScadaTimeSeries:
    return ScadaTimeSeries(
        sensor_id="sensor-A",
        sample_count=720,
        sample_interval_sec=60.0,
    )


@pytest.fixture
def fixed_since() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)
