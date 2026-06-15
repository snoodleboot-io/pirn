"""Unit tests for :class:`TumorMicrobiotaClassifier`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry
from pirn_health.pathology.tumor_microbiota_classifier import TumorMicrobiotaClassifier

_CFG = KnotConfig(id="tm")
_SEQUENCE_DATA: dict[str, Any] = {
    "reads": ["ATCG", "GCTA", "TTAA"],
    "sample_id": "SAMP001",
}


def _make_knot() -> TumorMicrobiotaClassifier:
    with Tapestry():
        src = Parameter("seq", dict, default=_SEQUENCE_DATA, _config=KnotConfig(id="seq"))
        return TumorMicrobiotaClassifier(
            sequence_data=src,
            classifier_model="silva",
            confidence_threshold=0.8,
            taxonomic_level="genus",
            _config=_CFG,
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_dict_sequence_data(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "dict"):
            await knot.process(sequence_data="not-a-dict", classifier_model="silva", confidence_threshold=0.8, taxonomic_level="genus")  # type: ignore[arg-type]

    async def test_rejects_empty_classifier_model(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "classifier_model"):
            await knot.process(sequence_data=_SEQUENCE_DATA, classifier_model="", confidence_threshold=0.8, taxonomic_level="genus")

    async def test_rejects_out_of_range_confidence(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "confidence_threshold"):
            await knot.process(sequence_data=_SEQUENCE_DATA, classifier_model="silva", confidence_threshold=1.5, taxonomic_level="genus")

    async def test_rejects_invalid_taxonomic_level(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "taxonomic_level"):
            await knot.process(sequence_data=_SEQUENCE_DATA, classifier_model="silva", confidence_threshold=0.8, taxonomic_level="kingdom")

    async def test_returns_dict_with_required_keys(self) -> None:
        knot = _make_knot()
        out = await knot.process(sequence_data=_SEQUENCE_DATA, classifier_model="silva", confidence_threshold=0.8, taxonomic_level="genus")
        assert isinstance(out, dict)
        assert "sample_id" in out
        assert "classifications" in out
        assert "diversity_index" in out
        assert out["sample_id"] == "SAMP001"
        assert isinstance(out["classifications"], list)
        assert isinstance(out["diversity_index"], float)
