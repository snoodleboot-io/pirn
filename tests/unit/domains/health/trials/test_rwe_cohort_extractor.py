"""Unit tests for :class:`RWECohortExtractor`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.trials.rwe_cohort_extractor import RWECohortExtractor
from pirn.tapestry import Tapestry


@knot
async def emit_patients() -> list[dict[str, Any]]:
    return [
        {"patient_id": "P1", "age": 65, "diagnosis": "T2D", "index_date": "2024-01-01"},
        {"patient_id": "P2", "age": 30, "diagnosis": "T2D", "index_date": "2024-02-01"},
        {"patient_id": "P3", "age": 70, "diagnosis": "T2D", "index_date": "2024-03-01", "excluded": True},
    ]


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_patient_data(self) -> None:
        with self.assertRaisesRegex(TypeError, "patient_data"):
            RWECohortExtractor(
                patient_data="not-a-knot",  # type: ignore[arg-type]
                inclusion_criteria={"diagnosis": "T2D"},
                exclusion_criteria={},
                index_date_col="index_date",
                _config=KnotConfig(id="r"),
            )

    def test_rejects_non_dict_inclusion_criteria(self) -> None:
        with Tapestry():
            p = emit_patients(_config=KnotConfig(id="p"))
            with self.assertRaisesRegex(TypeError, "inclusion_criteria"):
                RWECohortExtractor(
                    patient_data=p,
                    inclusion_criteria="wrong",  # type: ignore[arg-type]
                    exclusion_criteria={},
                    index_date_col="index_date",
                    _config=KnotConfig(id="r"),
                )

    def test_rejects_non_dict_exclusion_criteria(self) -> None:
        with Tapestry():
            p = emit_patients(_config=KnotConfig(id="p"))
            with self.assertRaisesRegex(TypeError, "exclusion_criteria"):
                RWECohortExtractor(
                    patient_data=p,
                    inclusion_criteria={},
                    exclusion_criteria="wrong",  # type: ignore[arg-type]
                    index_date_col="index_date",
                    _config=KnotConfig(id="r"),
                )

    def test_rejects_empty_index_date_col(self) -> None:
        with Tapestry():
            p = emit_patients(_config=KnotConfig(id="p"))
            with self.assertRaisesRegex(ValueError, "index_date_col"):
                RWECohortExtractor(
                    patient_data=p,
                    inclusion_criteria={},
                    exclusion_criteria={},
                    index_date_col="",
                    _config=KnotConfig(id="r"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict_with_required_keys(self) -> None:
        with Tapestry() as t:
            p = emit_patients(_config=KnotConfig(id="p"))
            RWECohortExtractor(
                patient_data=p,
                inclusion_criteria={"diagnosis": "T2D"},
                exclusion_criteria={"excluded": True},
                index_date_col="index_date",
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["r"]
        assert isinstance(out, dict)
        assert "cohort" in out
        assert "n_included" in out
        assert "n_excluded" in out
        assert "exclusion_reasons" in out

    async def test_exclusion_applied(self) -> None:
        with Tapestry() as t:
            p = emit_patients(_config=KnotConfig(id="p"))
            RWECohortExtractor(
                patient_data=p,
                inclusion_criteria={"diagnosis": "T2D"},
                exclusion_criteria={"excluded": True},
                index_date_col="index_date",
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["r"]
        assert out["n_included"] == 2
        assert out["n_excluded"] == 1
