"""``_ClaimVerification`` — search a memory store for support of one claim.

Internal per-claim knot for
:class:`~pirn_agents.specializations.guardrails.fact_claim_verifier.FactClaimVerifier`'s
fan-out (PIR-867): each claim's search is independent of every other claim's,
so it is one node per claim rather than a hand-rolled ``for`` loop awaiting
``store.search`` directly.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.stores.memory_store import MemoryStore


class _ClaimVerification(Knot):
    """Search the memory store for one claim; ``True`` when at least one hit."""

    def __init__(
        self,
        *,
        claim: Knot | str,
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(claim=claim, store=store, _config=_config, **kwargs)

    async def process(self, claim: str, store: MemoryStore, **_: Any) -> bool:
        """Return whether ``claim`` has at least one supporting hit in ``store``."""
        hits = await store.search(claim, top_k=1)
        return bool(hits)
