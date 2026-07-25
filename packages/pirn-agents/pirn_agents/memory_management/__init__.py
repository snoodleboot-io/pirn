"""Advanced memory *management* on top of the F4 stores and ``memory_patterns/``.

This package adds memory lifecycle — not new memory *types* — over the existing
:class:`~pirn_agents.memory_store.MemoryStore` interface and the
``specializations/memory_patterns/`` pipelines:

* **Typed records + provenance** (S5) — :class:`MemoryRecord` /
  :class:`MemoryProvenance`, the value objects every other piece speaks.
* **Consolidation** (S1) — episodic → deduplicated semantic facts, built on the
  F17 :class:`~pirn_agents.context.summarizer.Summarizer` seam.
* **Decay / eviction** (S2) — importance+recency scoring with TTL and low-value
  eviction policies that bound store growth.
* **Cross-session profiles** (S3) — durable per-user/per-entity aggregation keyed
  by a provider-neutral session-key abstraction (the F14 seam).
* **Ranked recall** (S4) — relevance + recency + importance fusion over recall
  candidates, with an optional F4 rerank hook.

Following the sibling ``memory_patterns`` convention, classes are imported by
their fully-qualified module path rather than re-exported here.
"""

__all__: list[str] = []
