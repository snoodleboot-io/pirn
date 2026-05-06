"""``HallucinationDetector`` — detect unsupported claims against source documents.

A :class:`Knot` that sends an :class:`AgentResponse` and a list of
source document strings to an LLM and asks it to identify any claims in
the response that are not supported by the sources. Returns a detection
result mapping containing ``"flagged_claims"`` (list of strings) and
``"has_hallucinations"`` (bool).

Algorithm:
    1. Validate that ``response`` is an :class:`AgentResponse`; raise
       :class:`TypeError` otherwise.
    2. Enumerate ``sources`` as numbered passages ``[Source N]: ...``.
    3. Build a hallucination-detection prompt instructing the LLM to list
       any claim in ``response.content`` not supported by the sources, one
       per line, or reply ``"NONE"`` if all claims are supported.
    4. Send the prompt to the :class:`LLMProvider` and extract the text from
       the reply.
    5. If the text (upper-cased) equals ``"NONE"`` or is empty, return
       ``{"flagged_claims": [], "has_hallucinations": False}``.
    6. Otherwise split on newlines, strip whitespace and list markers, discard
       empty lines, and return ``{"flagged_claims": [...], "has_hallucinations": True}``.


References:
    - pirn-native: :class:`pirn.domains.agents.llm_provider.LLMProvider`
    - pirn-native: :class:`pirn.domains.agents.types.agent_response.AgentResponse`
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
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(response=response, sources=sources, llm=llm, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        sources: Sequence[str],
        llm: LLMProvider,
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
        sources_text = "\n\n".join(f"[Source {i + 1}]: {src}" for i, src in enumerate(sources))
        prompt = (
            "You are a hallucination detector. Given the sources and a response, "
            "list any claims in the response that are NOT supported by the sources.\n"
            "Return one unsupported claim per line. If all claims are supported, "
            "reply with exactly: NONE\n\n"
            f"Sources:\n{sources_text}\n\n"
            f"Response:\n{response.content}"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
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
                    cleaned = cleaned[len(marker) :].strip()
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
