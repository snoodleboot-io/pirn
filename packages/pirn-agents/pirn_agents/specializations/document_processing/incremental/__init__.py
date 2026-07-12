"""Incremental indexing: upsert-by-hash + freshness/TTL (F25-S4 / PIR-581).

Content-hash change detection so only new/changed chunks are re-embedded
(:class:`~pirn_agents.specializations.document_processing.incremental.incremental_upserter.IncrementalUpserter`
and its
:class:`~pirn_agents.specializations.document_processing.incremental.upsert_plan.UpsertPlan`),
plus a TTL/staleness
:class:`~pirn_agents.specializations.document_processing.incremental.freshness_policy.FreshnessPolicy`
that flags aged documents for refresh. Backend-free: it operates over the
neutral ``MemoryStore`` interface.
"""

from __future__ import annotations

from pirn_agents.specializations.document_processing.incremental.freshness_policy import (
    FreshnessPolicy,
)
from pirn_agents.specializations.document_processing.incremental.incremental_upserter import (
    IncrementalUpserter,
)
from pirn_agents.specializations.document_processing.incremental.upsert_plan import (
    UpsertPlan,
)

__all__: list[str] = [
    "FreshnessPolicy",
    "IncrementalUpserter",
    "UpsertPlan",
]
