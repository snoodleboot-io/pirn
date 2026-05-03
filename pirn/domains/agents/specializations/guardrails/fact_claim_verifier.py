"""``FactClaimVerifier`` — search a memory store for support of each claim.

Inner stage knot used by :class:`FactCheckGate`. Queries the
configured :class:`MemoryStore` once per claim. Claims that return
zero hits are recorded as unverified; the original
:class:`AgentResponse` is returned with a warning footer appended
when at least one claim could not be verified.
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
        store: MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "FactClaimVerifier: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        self._store = store
        super().__init__(
            response=response,
            claims=claims,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        response: AgentResponse,
        claims: Sequence[str],
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
            iterator = self._store.search(claim, top_k=1)
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
        warning = (
            "\n\n[fact_check_gate] Unverified claims:\n" + warning_lines
        )
        return AgentResponse(
            content=response.content + warning,
            tool_calls=response.tool_calls,
            finish_reason=response.finish_reason,
            usage=response.usage,
        )
