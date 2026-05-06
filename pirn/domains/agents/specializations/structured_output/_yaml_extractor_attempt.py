"""``_YamlExtractorAttempt`` — internal helper Knot for :class:`YamlExtractorPipeline`.

Single LLM attempt: builds the YAML prompt, calls the LLM, parses the
YAML response, and returns either the parsed mapping or an error string
for downstream retry. Internal API.

Algorithm:
    1. Receive ``prompt`` (string), ``llm``, optional ``schema`` mapping, and ``prior_error``.
    2. Build a system message instructing the LLM to reply with a valid YAML document.
    3. If ``schema`` is provided, append the schema constraint to the system message.
    4. If ``prior_error`` is non-empty, append corrective feedback.
    5. Call the LLM provider with the constructed chat messages.
    6. Parse the response text as YAML using :func:`yaml.safe_load`.
    7. Validate that the root is a mapping and all schema keys are present (if schema given).
    8. Return the parsed mapping on success, or an error string on failure.


References:
    - PyYAML :func:`yaml.safe_load`:
      https://pyyaml.org/wiki/PyYAMLDocumentation
    - :class:`pirn.domains.agents.llm_provider.LLMProvider`
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import yaml

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class _YamlExtractorAttempt(Knot):
    """Single LLM attempt: build the YAML prompt, call the LLM, parse YAML."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        schema: Knot | Mapping[str, Any] | None,
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
        schema: Mapping[str, Any] | None,
        prior_error: str,
        **_: Any,
    ) -> Mapping[str, Any] | str:
        """Call the LLM, parse the YAML reply, and return the mapping or an error string.

        Args:
            prompt: The extraction prompt string sent to the LLM as a user message.
            llm: The LLM provider to call.
            schema: Optional mapping of expected top-level field names, or None.
            prior_error: Error string from a previous failed attempt, or empty string.

        Returns:
            The parsed YAML mapping on success, or an error description string on failure.

        Raises:
            TypeError: If prompt is not a string.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                f"YamlExtractorPipeline: prompt must be a string, got {type(prompt).__name__}"
            )
        schema_dict: dict[str, Any] | None = dict(schema) if schema is not None else None
        system_lines = [
            "You are a structured-output assistant.",
            "Reply with a single valid YAML document only — no prose, no fences.",
        ]
        if schema_dict is not None:
            system_lines.append(
                "The YAML mapping must conform to this schema: "
                f"{json.dumps(schema_dict, sort_keys=True)}"
            )
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
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            return f"invalid YAML: {exc}"
        if not isinstance(parsed, dict):
            return f"expected YAML mapping at the root, got {type(parsed).__name__}"
        if schema_dict is not None:
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
