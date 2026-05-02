"""``ClinicalNLPExtractor`` — extract structured fields from clinical notes.

Wraps an :class:`LLMProvider`; the production path crafts a clinical-
extraction prompt and parses the JSON response. The stub returns an
empty mapping so downstream knots see the right shape without a live
LLM call.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class ClinicalNLPExtractor(Knot):
    """Extract diagnoses / medications / vitals from a clinical note."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        note_text: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(provider, LLMProvider):
            raise TypeError(
                "ClinicalNLPExtractor: provider must be an LLMProvider"
            )
        if not isinstance(note_text, str):
            raise TypeError(
                "ClinicalNLPExtractor: note_text must be a string"
            )
        if not note_text:
            raise ValueError(
                "ClinicalNLPExtractor: note_text must be non-empty"
            )
        self._provider = provider
        self._note_text = note_text
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, Any]:
        # Production: send a structured-output prompt to the LLM and parse
        # the JSON response into diagnoses / medications / vitals.
        return {
            "diagnoses": (),
            "medications": (),
            "vitals": (),
        }
