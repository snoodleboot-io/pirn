"""Unit tests for :class:`ICD10CodeValidator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.icd10_code_validator import (
    ICD10CodeValidator,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="codes"):
            ICD10CodeValidator(
                codes=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="v"),
            )

    def test_rejects_non_string(self) -> None:
        with pytest.raises(TypeError, match="string"):
            ICD10CodeValidator(
                codes=[1],  # type: ignore[list-item]
                _config=KnotConfig(id="v"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_valid_codes_returns_true(self) -> None:
        with Tapestry() as t:
            ICD10CodeValidator(
                codes=["E11.9", "I10"],
                _config=KnotConfig(id="v"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["v"]
        assert isinstance(out, bool)
        assert out is True

    async def test_invalid_codes_returns_false(self) -> None:
        with Tapestry() as t:
            ICD10CodeValidator(
                codes=["totally invalid"],
                _config=KnotConfig(id="v"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["v"]
        assert out is False
