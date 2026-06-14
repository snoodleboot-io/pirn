"""``FormatCoercer`` — coerce AgentResponse content to a target format via LLM.

A :class:`Knot` that checks whether an :class:`AgentResponse` content
already satisfies the requested format (``"json"``, ``"yaml"``, or
``"markdown"``). If not, it asks an LLM to rewrite the content in the
target format and returns an updated :class:`AgentResponse`.

Algorithm:
    1. Receive ``response`` (:class:`AgentResponse`), ``llm``, and ``target_format``.
    2. Validate ``llm`` is an :class:`LLMProvider` and ``target_format`` is supported.
    3. If the response content already matches the target format, return it unchanged.
    4. Otherwise, build a rewrite prompt and call the LLM.
    5. Wrap the rewritten content in a new :class:`AgentResponse` preserving metadata.


References:
    - :class:`pirn.core.providers.llm_provider.LLMProvider`
    - :class:`pirn.domains.agents.types.agent_response.AgentResponse`
"""

from __future__ import annotations

import json
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class FormatCoercer(Knot):
    """Rewrite AgentResponse content to a target format via LLM if needed."""

    _supported_formats: frozenset[str] = frozenset({"json", "yaml", "markdown"})

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        llm: Knot | LLMProvider,
        target_format: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            response=response, llm=llm, target_format=target_format, _config=_config, **kwargs
        )

    async def process(
        self,
        response: AgentResponse,
        llm: LLMProvider,
        target_format: str,
        **_: Any,
    ) -> AgentResponse:
        """Return the response as-is if already in target format, else rewrite via LLM.

        Args:
            response: The agent response whose content may need format coercion.
            llm: The LLM provider to use for rewriting.
            target_format: The target format string (``"json"``, ``"yaml"``, or ``"markdown"``).

        Returns:
            The original AgentResponse if already in target format, else a new
            AgentResponse with the rewritten content.

        Raises:
            TypeError: If llm is not an LLMProvider or response is not an AgentResponse.
            ValueError: If target_format is not a supported format.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"FormatCoercer: llm must be an LLMProvider, got {type(llm).__name__}")
        if target_format not in type(self)._supported_formats:
            raise ValueError(
                f"FormatCoercer: target_format must be one of "
                f"{sorted(type(self)._supported_formats)}, got {target_format!r}"
            )
        if not isinstance(response, AgentResponse):
            raise TypeError(
                f"FormatCoercer: response must be an AgentResponse, got {type(response).__name__}"
            )
        if self._already_matches(response.content, target_format):
            return response
        prompt = (
            f"Rewrite the following content in {target_format} format. "
            "Return only the reformatted content with no additional commentary.\n\n"
            f"Content:\n{response.content}"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        new_content = self._extract_text(raw).strip()
        return AgentResponse(
            content=new_content,
            tool_calls=response.tool_calls,
            finish_reason=response.finish_reason,
            usage=response.usage,
        )

    @staticmethod
    def _already_matches(content: str, target_format: str) -> bool:
        if target_format == "json":
            try:
                json.loads(content)
                return True
            except (json.JSONDecodeError, ValueError):
                return False
        if target_format == "yaml":
            stripped = content.strip()
            return stripped.startswith("---") or ":" in stripped
        if target_format == "markdown":
            stripped = content.strip()
            return (
                stripped.startswith("#")
                or stripped.startswith("**")
                or stripped.startswith("-")
                or "```" in stripped
            )
        return False

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
