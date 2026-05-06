"""Unit tests for :class:`FHIRPatientIngestor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.fhir_patient_ingestor import (
    FHIRPatientIngestor,
)
from tests.unit.domains.health.conftest import StubFHIRClient

_CFG = KnotConfig(id="i")
_CLIENT = StubFHIRClient()


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_client(self) -> None:
        knot = FHIRPatientIngestor(client=_CLIENT, search_params={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "FHIRClient"):
            await knot.process(client="x", search_params={})  # type: ignore[arg-type]

    async def test_rejects_non_mapping_params(self) -> None:
        knot = FHIRPatientIngestor(client=_CLIENT, search_params={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "search_params"):
            await knot.process(client=_CLIENT, search_params=42)  # type: ignore[arg-type]

    async def test_returns_tuple_of_records(self) -> None:
        knot = FHIRPatientIngestor(client=_CLIENT, search_params={"family": "Smith"}, _config=_CFG)
        out = await knot.process(client=_CLIENT, search_params={"family": "Smith"})
        assert isinstance(out, tuple)
