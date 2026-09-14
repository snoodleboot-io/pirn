"""``FactClaimVerifier`` — search a memory store for support of each claim.

Inner stage knot used by :class:`FactCheck`. Each claim's search is
independent of every other claim's, so this is a fan-out — one
:class:`~pirn_agents.specializations.guardrails.claim_verification.ClaimVerification`
knot per claim wired into an :class:`~pirn.nodes.aggregator.Aggregator` — rather
than a hand-rolled ``for`` loop awaiting ``store.search`` directly (PIR-867;
before this, no claim's search had its own lineage row). Claims that return
zero hits are recorded as unverified; the original :class:`AgentResponse` is
returned with a warning footer appended when at least one claim could not be
verified.

Algorithm:
    1. Filter ``claims`` down to non-empty strings.
    2. When none remain, return a ``Parameter`` defaulting to the original
       ``response`` unchanged — an ``Aggregator`` requires at least one parent.
    3. Otherwise build one ``ClaimVerification`` per valid claim and wire
       them as the parents of an ``Aggregator``.
    4. The combine collects claims whose verification came back ``False``
       into ``unverified``. If empty, it returns ``response`` unchanged.
       Otherwise it builds a warning footer listing each unverified claim
       prefixed with ``"- "`` and returns a new :class:`AgentResponse` with
       the footer appended to the original content.


References:
    - pirn-native: :class:`pirn_agents.memory.stores.memory_store.MemoryStore`
    - pirn-native: :class:`pirn_agents.types.messaging.agent_response.AgentResponse`
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.guardrails.claim_verification import ClaimVerification
from pirn_agents.types.messaging.agent_response import AgentResponse


class FactClaimVerifier(AgentPipeline):
    """Verifies each claim against a :class:`MemoryStore` and annotates."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        claims: Knot | Sequence[str],
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            response=response,
            claims=claims,
            store=store,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        response: AgentResponse,
        claims: Sequence[str],
        store: MemoryStore,
        **_: Any,
    ) -> Knot:
        """Wire one verification knot per valid claim and return the annotating sink.

        Args:
            response: The original agent response to annotate.
            claims: The list of factual claims to verify against the memory store.
            store: The memory store searched once per claim.

        Returns:
            The sink of the inner pipeline: a ``Parameter`` defaulting to
            ``response`` unchanged when no valid claim remains, or an
            :class:`Aggregator` over one ``ClaimVerification`` per claim
            whose output is ``response`` (unchanged if every claim verified,
            or annotated with an unverified-claims warning otherwise).
        """
        valid_claims = [claim for claim in claims if claim]
        if not valid_claims:
            return Parameter(
                "original", AgentResponse, default=response, _config=KnotConfig(id="original")
            )
        per_claim: dict[str, Knot] = {
            f"claim_{index}": ClaimVerification(
                claim=claim, store=store, _config=KnotConfig(id=f"verify_{index}")
            )
            for index, claim in enumerate(valid_claims)
        }
        return Aggregator(
            combine=functools.partial(self._annotate, response, valid_claims),
            _config=KnotConfig(id="annotate"),
            **per_claim,
        )

    @staticmethod
    def _annotate(
        response: AgentResponse, claims: Sequence[str], **verified_by_key: bool
    ) -> AgentResponse:
        """Return ``response``, or a copy annotated with unverified claims."""
        unverified = [
            claim for index, claim in enumerate(claims) if not verified_by_key[f"claim_{index}"]
        ]
        if not unverified:
            return response
        warning_lines = "\n".join(f"- {claim}" for claim in unverified)
        warning = "\n\n[fact_check] Unverified claims:\n" + warning_lines
        return AgentResponse(
            content=response.data + warning,
            tool_calls=response.metadata.tool_calls,
            finish_reason=response.metadata.finish_reason,
            usage=response.metadata.usage,
        )
