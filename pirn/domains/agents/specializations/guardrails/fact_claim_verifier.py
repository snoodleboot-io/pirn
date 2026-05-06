"""``FactClaimVerifier`` — search a memory store for support of each claim.

Inner stage knot used by :class:`FactCheckGate`. Queries the
configured :class:`MemoryStore` once per claim. Claims that return
zero hits are recorded as unverified; the original
:class:`AgentResponse` is returned with a warning footer appended
when at least one claim could not be verified.

Algorithm:
    1. Validate that ``response`` is an :class:`AgentResponse`; raise
       :class:`TypeError` otherwise.
    2. Iterate over ``claims``; skip any entry that is not a non-empty string.
    3. For each valid claim, call ``store.search(claim, top_k=1)``; await the
       result if it is awaitable and consume at most one item from the iterator.
    4. Collect claims that produced zero hits into ``unverified``.
    5. If ``unverified`` is empty, return ``response`` unchanged.
    6. Otherwise build a warning footer listing each unverified claim prefixed
       with ``"- "`` and return a new :class:`AgentResponse` with the footer
       appended to the original content.


References:
    - pirn-native: :class:`pirn.domains.agents.memory_store.MemoryStore`
    - pirn-native: :class:`pirn.domains.agents.types.agent_response.AgentResponse`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.types.agent_response import AgentResponse


class FactClaimVerifier(Knot):
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
    ) -> AgentResponse:
        """Search the memory store for each claim and return the response with a warning footer for unverified ones.

        Args:
            response: The original agent response to annotate.
            claims: The list of factual claims to verify against the memory store.

        Returns:
            The original AgentResponse if all claims are supported, or a copy with an unverified-claims warning appended.

        Raises:
            TypeError: If response is not an AgentResponse instance.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "FactClaimVerifier: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        unverified: list[str] = []
        for claim in claims:
            if not isinstance(claim, str) or not claim:
                continue
            iterator = store.search(claim, top_k=1)
            if hasattr(iterator, "__await__"):
                iterator = await iterator  # type: ignore[assignment]
            hits: list[Any] = []
            if hasattr(iterator, "__aiter__"):
                async for hit in iterator:
                    hits.append(hit)
                    break
            elif isinstance(iterator, list):
                hits = list(iterator[:1])
            if not hits:
                unverified.append(claim)
        if not unverified:
            return response
        warning_lines = "\n".join(f"- {claim}" for claim in unverified)
        warning = "\n\n[fact_check_gate] Unverified claims:\n" + warning_lines
        return AgentResponse(
            content=response.content + warning,
            tool_calls=response.tool_calls,
            finish_reason=response.finish_reason,
            usage=response.usage,
        )
