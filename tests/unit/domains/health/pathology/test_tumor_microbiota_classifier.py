"""Unit tests for :class:`TumorMicrobiotaClassifier`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.pathology.tumor_microbiota_classifier import TumorMicrobiotaClassifier
from pirn.tapestry import Tapestry


@knot
async def emit_sequence_data() -> dict[str, Any]:
    return {
        "reads": ["ATCG", "GCTA", "TTAA"],
        "sample_id": "SAMP001",
    }


class TestConstruction:
    def test_rejects_non_knot_sequence_data(self) -> None:
        with pytest.raises(TypeError, match="sequence_data"):
            TumorMicrobiotaClassifier(
                sequence_data="not-a-knot",  # type: ignore[arg-type]
                classifier_model="silva",
                confidence_threshold=0.8,
                taxonomic_level="genus",
                _config=KnotConfig(id="tm"),
            )

    def test_rejects_empty_classifier_model(self) -> None:
        with Tapestry():
            s = emit_sequence_data(_config=KnotConfig(id="s"))
            with pytest.raises(ValueError, match="classifier_model"):
                TumorMicrobiotaClassifier(
                    sequence_data=s,
                    classifier_model="",
                    confidence_threshold=0.8,
                    taxonomic_level="genus",
                    _config=KnotConfig(id="tm"),
                )

    def test_rejects_out_of_range_confidence(self) -> None:
        with Tapestry():
            s = emit_sequence_data(_config=KnotConfig(id="s"))
            with pytest.raises(ValueError, match="confidence_threshold"):
                TumorMicrobiotaClassifier(
                    sequence_data=s,
                    classifier_model="silva",
                    confidence_threshold=1.5,
                    taxonomic_level="genus",
                    _config=KnotConfig(id="tm"),
                )

    def test_rejects_invalid_taxonomic_level(self) -> None:
        with Tapestry():
            s = emit_sequence_data(_config=KnotConfig(id="s"))
            with pytest.raises(ValueError, match="taxonomic_level"):
                TumorMicrobiotaClassifier(
                    sequence_data=s,
                    classifier_model="silva",
                    confidence_threshold=0.8,
                    taxonomic_level="kingdom",
                    _config=KnotConfig(id="tm"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_dict_with_required_keys(self) -> None:
        with Tapestry() as t:
            s = emit_sequence_data(_config=KnotConfig(id="s"))
            TumorMicrobiotaClassifier(
                sequence_data=s,
                classifier_model="silva",
                confidence_threshold=0.8,
                taxonomic_level="genus",
                _config=KnotConfig(id="tm"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["tm"]
        assert isinstance(out, dict)
        assert "sample_id" in out
        assert "classifications" in out
        assert "diversity_index" in out
        assert out["sample_id"] == "SAMP001"
        assert isinstance(out["classifications"], list)
        assert isinstance(out["diversity_index"], float)
