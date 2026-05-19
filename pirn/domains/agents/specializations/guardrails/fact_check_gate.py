"""``FactCheckGate`` — cross-reference response claims against memory.

A :class:`SubTapestry` that:

1. Asks an LLM (via :class:`FactClaimExtractor`) to enumerate the
   factual claims contained in the supplied
   :class:`AgentResponse.content`.
2. Searches the configured :class:`MemoryStore` for each claim (via
   :class:`FactClaimVerifier`) and appends a warning footer when one
   or more claims have no supporting hit.

The pipeline returns either the original :class:`AgentResponse` (all
claims supported) or a copy with the warning footer appended.

Algorithm:
    1. Run an inner :class:`Tapestry` containing :class:`FactClaimExtractor`
       followed by :class:`FactClaimVerifier`.
    2. :class:`FactClaimExtractor` prompts the LLM to enumerate one claim per
       line from the response content and returns a ``list[str]``.
    3. :class:`FactClaimVerifier` queries the :class:`MemoryStore` (``top_k=1``)
       for each claim; claims with zero hits are collected as unverified.
    4. If all claims are verified, return the original :class:`AgentResponse`
       unchanged; otherwise return a copy with a warning footer listing the
       unverified claims appended to the content.


References:
    - pirn-native: :class:`pirn.domains.agents.specializations.guardrails.fact_claim_extractor.FactClaimExtractor`
    - pirn-native: :class:`pirn.domains.agents.specializations.guardrails.fact_claim_verifier.FactClaimVerifier`
    - pirn-native: :class:`pirn.domains.agents.memory_store.MemoryStore`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.guardrails.fact_claim_extractor import (
    FactClaimExtractor,
)
from pirn.domains.agents.specializations.guardrails.fact_claim_verifier import (
    FactClaimVerifier,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry


class FactCheckGate(SubTapestry):
    """LLM-assisted claim extraction + memory-store verification."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        store: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(response=response, store=store, llm=llm, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        store: MemoryStore,
        llm: LLMProvider,
        **_: Any,
    ) -> Any:
        """Extract factual claims from the response and return it annotated with any unverified claims.

        Args:
            response: The agent response whose content is fact-checked.

        Returns:
            The original AgentResponse if all claims are verified, or a copy with a warning footer listing unverified claims.

        Raises:
            RuntimeError: If the inner verifier does not return an AgentResponse.
        """
        claims = FactClaimExtractor(
            response=response,
            llm=llm,
            _config=KnotConfig(id="claims"),
        )
        return FactClaimVerifier(
            response=response,
            claims=claims,
            store=store,
            _config=KnotConfig(id="verify"),
        )
