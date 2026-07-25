"""``_JsonExtractorAttempt`` — internal helper Knot for :class:`JsonExtractorPipeline`.

Single LLM attempt: builds the prompt, calls the LLM, parses JSON, and
returns either the parsed mapping or an error string for downstream
retry. Internal API.

Algorithm:
    1. Receive ``prompt`` (string), ``llm``, ``schema`` mapping, and ``prior_error`` string.
    2. Build a system message instructing the LLM to reply with valid JSON.
    3. If ``prior_error`` is non-empty, append corrective feedback to the system message.
    4. Call the LLM provider with the constructed chat messages.
    5. Parse the response text as JSON.
    6. Validate that the root is a dict and all schema keys are present.
    7. Return the parsed mapping on success, or an error string on failure.


References:
    - :mod:`json` — Python standard library JSON parser
    - :class:`pirn_agents.llm_provider.LLMProvider`
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider


class _JsonExtractorAttempt(Knot):
    """Single LLM attempt: build the prompt, call the LLM, parse JSON."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        schema: Knot | Mapping[str, Any],
        prior_error: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prompt=prompt,
            llm=llm,
            schema=schema,
            prior_error=prior_error,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        prompt: str,
        llm: LLMProvider,
        schema: Mapping[str, Any],
        prior_error: str,
        **_: Any,
    ) -> Mapping[str, Any] | str:
        """Call the LLM, parse the JSON reply, and return the mapping or an error string.

        Args:
            prompt: The extraction prompt string sent to the LLM as a user message.
            llm: The LLM provider to call.
            schema: Mapping of expected top-level field names.
            prior_error: Error string from a previous failed attempt, or empty string.

        Returns:
            The parsed JSON mapping on success, or an error description string on failure.

        Raises:
            TypeError: If prompt is not a string.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                f"JsonExtractorPipeline: prompt must be a string, got {type(prompt).__name__}"
            )
        schema_dict = dict(schema)
        system_lines = [
            "You are a structured-output assistant.",
            "Reply with a single valid JSON object only — no prose, no fences.",
            "The JSON object must conform to this schema:",
            json.dumps(schema_dict, sort_keys=True),
        ]
        if prior_error:
            system_lines.append(
                f"The previous attempt failed: {prior_error}. Correct the error and respond again."
            )
        chat_messages = [
            {"role": "system", "content": "\n".join(system_lines)},
            {"role": "user", "content": prompt},
        ]
        raw = await llm.chat(chat_messages)
        text = self._extract_text(raw)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return f"invalid JSON: {exc.msg}"
        if not isinstance(parsed, dict):
            return f"expected JSON object at the root, got {type(parsed).__name__}"
        missing = [key for key in schema_dict if key not in parsed]
        if missing:
            return f"missing required keys: {sorted(missing)}"
        return parsed

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    text = first.get("text")
                    if isinstance(text, str):
                        return text
                if isinstance(first, str):
                    return first
            text = raw.get("text")
            if isinstance(text, str):
                return text
        return str(raw)
