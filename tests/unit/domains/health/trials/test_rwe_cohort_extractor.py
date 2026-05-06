"""Unit tests for :class:`RWECohortExtractor`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.trials.rwe_cohort_extractor import RWECohortExtractor
from pirn.tapestry import Tapestry

_PATIENTS: list[dict[str, Any]] = [
    {"patient_id": "P1", "age": 65, "diagnosis": "T2D", "index_date": "2024-01-01"},
    {"patient_id": "P2", "age": 30, "diagnosis": "T2D", "index_date": "2024-02-01"},
    {
        "patient_id": "P3",
        "age": 70,
        "diagnosis": "T2D",
        "index_date": "2024-03-01",
        "excluded": True,
    },
]


def _make_knot() -> RWECohortExtractor:
    with Tapestry():
        from pirn.core.parameter import Parameter
        src = Parameter("p", list, default=_PATIENTS, _config=KnotConfig(id="p"))
        return RWECohortExtractor(
            patient_data=src,
            inclusion_criteria={"diagnosis": "T2D"},
            exclusion_criteria={},
            index_date_col="index_date",
            _config=KnotConfig(id="r"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_index_date_col(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "index_date_col"):
            await knot.process(
                patient_data=_PATIENTS,
                inclusion_criteria={},
                exclusion_criteria={},
                index_date_col="",
            )

    async def test_returns_dict_with_required_keys(self) -> None:
        knot = _make_knot()
        out = await knot.process(
            patient_data=_PATIENTS,
            inclusion_criteria={"diagnosis": "T2D"},
            exclusion_criteria={"excluded": True},
            index_date_col="index_date",
        )
        assert isinstance(out, dict)
        assert "cohort" in out
        assert "n_included" in out
        assert "n_excluded" in out
        assert "exclusion_reasons" in out

    async def test_exclusion_applied(self) -> None:
        knot = _make_knot()
        out = await knot.process(
            patient_data=_PATIENTS,
            inclusion_criteria={"diagnosis": "T2D"},
            exclusion_criteria={"excluded": True},
            index_date_col="index_date",
        )
        assert out["n_included"] == 2
        assert out["n_excluded"] == 1
