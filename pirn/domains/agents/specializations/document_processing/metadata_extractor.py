"""``MetadataExtractor`` — extract structured metadata from a document via LLM.

A :class:`Knot` that sends a document string to an LLM with a
structured extraction prompt and returns a dict containing the fields
``title``, ``author``, ``date``, and ``summary``. Missing fields are
returned as ``None``.

Algorithm:
    1. Build a structured extraction prompt instructing the LLM to return a JSON
       object with keys ``title``, ``author``, ``date``, and ``summary``.
    2. Send the prompt together with the full document text to the ``LLMProvider``.
    3. Parse the LLM response: extract the first JSON object found via regex, then
       call ``json.loads``.
    4. Return a dict with the four keys; any key absent from the parsed JSON is
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
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class MetadataExtractor(Knot):
    """Extract title, author, date, and summary from a document via LLM."""

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
            TypeError: If document is not a string.
        """
        if not isinstance(document, str):
            raise TypeError(
                "MetadataExtractor: document must be a string, "
                f"got {type(document).__name__}"
            )
        prompt = (
            "Extract metadata from the document below.\n"
            "Return a JSON object with these keys: "
            "title, author, date, summary.\n"
            "Use null for any field that cannot be determined.\n\n"
            f"Document:\n{document}"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        text = self._extract_text(raw).strip()
        parsed = self._parse_json(text)
        return {
            "title": parsed.get("title"),
            "author": parsed.get("author"),
            "date": parsed.get("date"),
            "summary": parsed.get("summary"),
        }

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        try:
            return dict(json.loads(text))
        except (json.JSONDecodeError, ValueError):
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return dict(json.loads(match.group()))
            except (json.JSONDecodeError, ValueError):
                pass
        return {}

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
