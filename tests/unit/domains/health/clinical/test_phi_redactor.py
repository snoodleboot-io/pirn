"""Unit tests for :class:`PHIRedactor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.phi_redactor import PHIRedactor
from pirn.domains.health.types.clinical_record import ClinicalRecord
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_record(self) -> None:
        with pytest.raises(TypeError, match="ClinicalRecord"):
            PHIRedactor(
                record="x",  # type: ignore[arg-type]
                salt="s",
                _config=KnotConfig(id="r"),
            )

    def test_rejects_non_string_salt(self) -> None:
        with pytest.raises(TypeError, match="salt"):
            PHIRedactor(
                record=ClinicalRecord(),
                salt=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="r"),
            )

    def test_rejects_empty_salt(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            PHIRedactor(
                record=ClinicalRecord(),
                salt="",
                _config=KnotConfig(id="r"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_redacted_record(self) -> None:
        with Tapestry() as t:
            PHIRedactor(
                record=ClinicalRecord(patient_id="P1", encounter_id="E1"),
                salt="seed",
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["r"]
        assert isinstance(out, ClinicalRecord)
        assert out.patient_id != "P1"
        assert out.encounter_id != "E1"
        assert len(out.patient_id) == 16
