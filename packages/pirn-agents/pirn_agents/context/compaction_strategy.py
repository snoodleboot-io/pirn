"""``CompactionStrategy`` — the stable seam for context compaction.

This is the one interface F27 (summary memory) builds on: given a
:class:`~pirn_agents.context.compaction_request.CompactionRequest`, a strategy
returns a :class:`~pirn_agents.context.compaction_result.CompactionResult`. The
contract is intentionally narrow and fixed so downstream memory implementations
can plug in new compaction behaviours (sliding-window, hierarchical summary,
embedding-clustered recap, …) without changing any caller.

Contract every strategy must honour:

* **Pinned content is never dropped** — items with ``pinned=True`` always
  appear in :attr:`CompactionResult.retained`.
* **Triggering is threshold-gated** — when fill is at or below
  ``fill_threshold * available`` the pass is a no-op
  (:attr:`CompactionResult.triggered` is ``False`` and ``retained == items``).
* **Compaction is lossless in intent** — evicted items are surfaced in
  :attr:`CompactionResult.evicted` and represented by the summary.
"""

from __future__ import annotations

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.context.compaction_request import CompactionRequest
from pirn_agents.context.compaction_result import CompactionResult


class CompactionStrategy(PirnOpaqueValue):
    """Interface every context-compaction strategy must satisfy."""

    async def compact(self, request: CompactionRequest) -> CompactionResult:
        """Compact ``request`` into a :class:`CompactionResult`.

        Implementations must preserve pinned content and treat ``request`` as
        read-only.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement compact()")
