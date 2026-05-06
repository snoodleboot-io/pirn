"""Unit tests for :class:`ClinicalNLPExtractor`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.clinical_nlp_extractor import (
    ClinicalNLPExtractor,
)
from tests.unit.domains.agents.conftest import StubLLMProvider


_CFG = KnotConfig(id="x")
_PROVIDER = StubLLMProvider(["ok"])


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_provider(self) -> None:
        knot = ClinicalNLPExtractor(provider=_PROVIDER, note_text="note", _config=_CFG)
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            await knot.process(provider="x", note_text="note")  # type: ignore[arg-type]

    async def test_rejects_non_string_note(self) -> None:
        knot = ClinicalNLPExtractor(provider=_PROVIDER, note_text="note", _config=_CFG)
        with self.assertRaisesRegex(TypeError, "note_text"):
            await knot.process(provider=_PROVIDER, note_text=42)  # type: ignore[arg-type]

    async def test_rejects_empty_note(self) -> None:
        knot = ClinicalNLPExtractor(provider=_PROVIDER, note_text="note", _config=_CFG)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(provider=_PROVIDER, note_text="")

    async def test_returns_mapping(self) -> None:
        knot = ClinicalNLPExtractor(provider=_PROVIDER, note_text="note", _config=_CFG)
        out = await knot.process(provider=_PROVIDER, note_text="The patient has fever.")
        assert isinstance(out, Mapping)
        assert "diagnoses" in out
        assert "medications" in out
        assert "vitals" in out
