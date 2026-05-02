"""``_YamlExtractorAttempt`` — internal helper Knot for :class:`YamlExtractorPipeline`.

Single LLM attempt: builds the YAML prompt, calls the LLM, parses the
YAML response, and returns either the parsed mapping or an error string
for downstream retry. Internal API.
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
        llm: LLMProvider,
        schema: Mapping[str, Any] | None,
        prior_error: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._llm = llm
        self._schema: dict[str, Any] | None = (
            dict(schema) if schema is not None else None
        )
        self._prior_error = prior_error
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(self, prompt: str, **_: Any) -> Mapping[str, Any] | str:
        if not isinstance(prompt, str):
            raise TypeError(
                "YamlExtractorPipeline: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        system_lines = [
            "You are a structured-output assistant.",
            "Reply with a single valid YAML document only — no prose, no fences.",
        ]
        if self._schema is not None:
            system_lines.append(
                "The YAML mapping must conform to this schema: "
                f"{json.dumps(self._schema, sort_keys=True)}"
            )
        if self._prior_error:
            system_lines.append(
                f"The previous attempt failed: {self._prior_error}. "
                "Correct the error and respond again."
            )
        chat_messages = [
            {"role": "system", "content": "\n".join(system_lines)},
            {"role": "user", "content": prompt},
        ]
        raw = await self._llm.chat(chat_messages)
        text = self._extract_text(raw)
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            return f"invalid YAML: {exc}"
        if not isinstance(parsed, dict):
            return (
                "expected YAML mapping at the root, got "
                f"{type(parsed).__name__}"
            )
        if self._schema is not None:
            missing = [key for key in self._schema if key not in parsed]
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
