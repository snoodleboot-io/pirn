"""Unit tests for :class:`FHIRPatientIngestor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.fhir_patient_ingestor import (
    FHIRPatientIngestor,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.health.conftest import StubFHIRClient


class TestConstruction(unittest.TestCase):
    def test_rejects_non_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "FHIRClient"):
            FHIRPatientIngestor(
                client="x",  # type: ignore[arg-type]
                search_params={},
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_mapping_params(self) -> None:
        with self.assertRaisesRegex(TypeError, "search_params"):
            FHIRPatientIngestor(
                client=StubFHIRClient(),
                search_params=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="i"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_tuple_of_records(self) -> None:
        with Tapestry() as t:
            FHIRPatientIngestor(
                client=StubFHIRClient(),
                search_params={"family": "Smith"},
                _config=KnotConfig(id="i"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, tuple)
