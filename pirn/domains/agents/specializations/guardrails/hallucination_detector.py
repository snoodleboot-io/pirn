"""``HallucinationDetector`` — detect unsupported claims against source documents.

A :class:`Knot` that sends an :class:`AgentResponse` and a list of
source document strings to an LLM and asks it to identify any claims in
the response that are not supported by the sources. Returns a detection
result mapping containing ``"flagged_claims"`` (list of strings) and
``"has_hallucinations"`` (bool).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class HallucinationDetector(Knot):
    """LLM-based hallucination detector against provided source documents."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        sources: Knot | Sequence[str],
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "HallucinationDetector: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        self._llm = llm
        super().__init__(
            response=response, sources=sources, _config=_config, **kwargs
        )

    async def process(
        self,
        response: AgentResponse,
        sources: Sequence[str],
        **_: Any,
    ) -> dict[str, Any]:
        """Check the response against sources and return a detection result.

        Args:
            response: The agent response to check for unsupported claims.
            sources: A sequence of source document strings to check against.

        Returns:
            A dict with 'flagged_claims' (list[str]) and 'has_hallucinations' (bool).

        Raises:
            TypeError: If response is not an AgentResponse instance.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "HallucinationDetector: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        sources_text = "\n\n".join(
            f"[Source {i + 1}]: {src}" for i, src in enumerate(sources)
        )
        prompt = (
            "You are a hallucination detector. Given the sources and a response, "
            "list any claims in the response that are NOT supported by the sources.\n"
            "Return one unsupported claim per line. If all claims are supported, "
            "reply with exactly: NONE\n\n"
            f"Sources:\n{sources_text}\n\n"
            f"Response:\n{response.content}"
        )
        raw = await self._llm.chat([{"role": "user", "content": prompt}])
        text = self._extract_text(raw).strip()
        if text.upper() == "NONE" or not text:
            return {"flagged_claims": [], "has_hallucinations": False}
        flagged: list[str] = []
        for line in text.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            for marker in ("- ", "* ", "• "):
                if cleaned.startswith(marker):
                    cleaned = cleaned[len(marker):].strip()
                    break
            if cleaned:
                flagged.append(cleaned)
        return {
            "flagged_claims": flagged,
            "has_hallucinations": bool(flagged),
        }

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
