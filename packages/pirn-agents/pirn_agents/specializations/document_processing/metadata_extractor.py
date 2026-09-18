"""``MetadataExtractor`` — extract structured metadata from a document via LLM.

A :class:`Knot` that sends a document string to an LLM with a
structured extraction prompt and returns a dict containing the fields
``title``, ``author``, ``date``, and ``summary``. Missing fields are
returned as ``None``.

Algorithm:
    1. Build a structured extraction prompt instructing the LLM to return a JSON
       object with keys ``title``, ``author``, ``date``, and ``summary``.
    2. Send the prompt together with the full document text to the ``LLMProvider``.
    3. Parse the LLM response as a JSON object; if the whole reply is not one,
       retry on the first brace-delimited span found by regex.
    4. Raise :class:`~pirn_agents.exceptions.llm_response_parse_error.LLMResponseParseError`
       when neither parses — a reply the extractor cannot read is a failed turn,
       not a document with no metadata.
    5. Return a dict with the four keys; any key absent from the parsed JSON is
       set to ``None``.

Math:
    No numeric computation — field extraction is purely a JSON parse of the LLM
    response with a regex-based JSON-block locator.

References:
    - Wei et al., 2022 — Chain-of-Thought Prompting Elicits Reasoning in Large
      Language Models (arXiv 2201.11903).
    - Kojima et al., 2022 — Large Language Models are Zero-Shot Reasoners
      (arXiv 2205.11916).
"""

from __future__ import annotations

import json
import re
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.shape_guard import ShapeGuard

from pirn_agents.exceptions.llm_response_parse_error import LLMResponseParseError
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText


class MetadataExtractor(Knot):
    """Extract title, author, date, and summary from a document via LLM."""

    _extraction_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.document_processing.metadata_extractor.extraction_prompt",
        default=(
            "Extract metadata from the document below.\n"
            "Return a JSON object with these keys: "
            "title, author, date, summary.\n"
            "Use null for any field that cannot be determined.\n\n"
            "Document:\n{{ document }}"
        ),
    )

    def __init__(
        self,
        *,
        document: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(document=document, llm=llm, _config=_config, **kwargs)

    async def process(
        self,
        document: str,
        llm: LLMProvider,
        **_: Any,
    ) -> dict[str, Any]:
        """Extract metadata fields from the document and return them as a dict.

        Args:
            document: The document text to extract metadata from.
            llm: The LLM provider to use for extraction.

        Returns:
            A dict with keys 'title', 'author', 'date', 'summary', each a string
            or None if not found.

        Raises:
            LLMResponseParseError: If the model's reply holds no JSON object.
        """
        prompt = type(self)._extraction_prompt.render(
            {"document": document},
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        text = LlmResponseText().extract(raw).strip()
        parsed = self._parse_json(text)
        return {
            "title": parsed.get("title"),
            "author": parsed.get("author"),
            "date": parsed.get("date"),
            "summary": parsed.get("summary"),
        }

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """Parse the reply as a JSON object, or the first JSON object inside it.

        Args:
            text: The model's reply.

        Returns:
            The parsed JSON object.

        Raises:
            LLMResponseParseError: If neither the whole reply nor the first
                brace-delimited span inside it parses as a JSON object.
        """
        try:
            return MetadataExtractor._as_json_object(text)
        except LLMResponseParseError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match is None:
                raise
            return MetadataExtractor._as_json_object(match.group())

    @staticmethod
    def _as_json_object(candidate: str) -> dict[str, Any]:
        """Parse ``candidate`` as a JSON object.

        Args:
            candidate: Text expected to be a JSON object.

        Returns:
            The parsed object as a plain dict.

        Raises:
            LLMResponseParseError: If ``candidate`` is not valid JSON, or is
                valid JSON that is not an object.
        """
        parsed: object
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise LLMResponseParseError(
                "MetadataExtractor: the model's reply is not valid JSON", candidate
            ) from exc
        if not ShapeGuard.is_str_keyed_dict(parsed):
            raise LLMResponseParseError(
                "MetadataExtractor: the model's reply is JSON but not an object, got "
                f"{type(parsed).__name__}",
                candidate,
            )
        return dict(parsed)
