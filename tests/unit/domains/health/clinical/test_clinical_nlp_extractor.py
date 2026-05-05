"""Unit tests for :class:`ClinicalNLPExtractor`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.clinical_nlp_extractor import (
    ClinicalNLPExtractor,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubLLMProvider


class TestConstruction(unittest.TestCase):
    def test_rejects_non_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            ClinicalNLPExtractor(
                provider="x",  # type: ignore[arg-type]
                note_text="note",
                _config=KnotConfig(id="x"),
            )

    def test_rejects_non_string_note(self) -> None:
        with self.assertRaisesRegex(TypeError, "note_text"):
            ClinicalNLPExtractor(
                provider=StubLLMProvider(["ok"]),
                note_text=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="x"),
            )

    def test_rejects_empty_note(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            ClinicalNLPExtractor(
                provider=StubLLMProvider(["ok"]),
                note_text="",
                _config=KnotConfig(id="x"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_mapping(self) -> None:
        with Tapestry() as t:
            ClinicalNLPExtractor(
                provider=StubLLMProvider(["ok"]),
                note_text="The patient has fever.",
                _config=KnotConfig(id="x"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["x"]
        assert isinstance(out, Mapping)
        assert "diagnoses" in out
        assert "medications" in out
        assert "vitals" in out
