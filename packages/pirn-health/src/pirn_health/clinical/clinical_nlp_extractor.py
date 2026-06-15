"""``ClinicalNLPExtractor`` — extract structured fields from clinical notes.

Wraps an :class:`LLMProvider`; the production path crafts a clinical-
extraction prompt and parses the JSON response. The stub returns an
empty mapping so downstream knots see the right shape without a live
LLM call.

Algorithm:
    1. Receive the LLMProvider and a note_text string.
    2. Validate that provider is an LLMProvider and note_text is non-empty.
    3. Send a structured-output prompt to the LLM.
    4. Parse the JSON response into diagnoses / medications / vitals.
    5. Return the extracted structured fields as a mapping.


References:
    - SNOMED CT: https://www.snomed.org/
    - ICD-10-CM: https://www.cdc.gov/nchs/icd/icd-10-cm.htm
    - RxNorm: https://www.nlm.nih.gov/research/umls/rxnorm/
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider


class ClinicalNLPExtractor(Knot):
    """Extract diagnoses / medications / vitals from a clinical note."""

    def __init__(
        self,
        *,
        provider: Knot | LLMProvider,
        note_text: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            provider=provider,
            note_text=note_text,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        provider: LLMProvider,
        note_text: str,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Send the clinical note to the LLM provider and return extracted diagnoses, medications, and vitals.

        Args:
            provider: LLM provider instance for sending the extraction prompt.
            note_text: Non-empty clinical note text to extract from.

        Returns:
            A mapping with keys ``diagnoses``, ``medications``, and ``vitals`` containing
            the structured fields extracted from the clinical note.

        Raises:
            TypeError: If provider is not an LLMProvider or note_text is not a string.
            ValueError: If note_text is empty.
        """
        if not isinstance(provider, LLMProvider):
            raise TypeError("ClinicalNLPExtractor: provider must be an LLMProvider")
        if not isinstance(note_text, str):
            raise TypeError("ClinicalNLPExtractor: note_text must be a string")
        if not note_text:
            raise ValueError("ClinicalNLPExtractor: note_text must be non-empty")
        messages = [
            {
                "role": "system",
                "content": "Extract diagnoses, medications, and vitals from the clinical note. Return JSON with keys diagnoses, medications, vitals (each a list of strings).",
            },
            {"role": "user", "content": note_text},
        ]
        response = await provider.chat(messages)
        try:
            data = json.loads(response.get("content", ""))
            return {
                "diagnoses": tuple(data.get("diagnoses", ())),
                "medications": tuple(data.get("medications", ())),
                "vitals": tuple(data.get("vitals", ())),
            }
        except (json.JSONDecodeError, TypeError, KeyError):
            return {"diagnoses": (), "medications": (), "vitals": ()}
