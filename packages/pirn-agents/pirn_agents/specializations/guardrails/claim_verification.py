"""``ClaimVerification`` — search a memory store for support of one claim.

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
from pirn_agents.specializations.guardrails.claim_support import ClaimSupport


class ClaimVerification(Knot):
    """Search the memory store for one claim and return the evidence found."""

    def __init__(
        self,
        *,
        claim: Knot | str,
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(claim=claim, store=store, _config=_config, **kwargs)

    async def process(self, claim: str, store: MemoryStore, **_: Any) -> ClaimSupport:
        """Search ``store`` for ``claim`` and return what it found.

        Args:
            claim: The claim to look up.
            store: The memory store searched.

        Returns:
            A :class:`ClaimSupport` whose ``data`` is the hits the search
            returned, so a downstream knot can cite them, and whose
            ``metadata.supported`` is the verdict. A bare ``bool`` would be
            core's ``Check`` role without ``Gate(check=)`` wiring (PIR-874).
        """
        hits = await store.search(claim, top_k=1)
        return ClaimSupport(claim, hits)
