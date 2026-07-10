"""Opt-in result/semantic caching keyed off DAG content-addressing.

Provider-neutral caching for the two idempotent hot paths the ADR calls out —
embedding lookups and side-effect-free tool calls. A
:class:`~pirn_agents.caching.result_cache.ResultCache` interface with an
in-memory default keys entries by a content address of their inputs; a semantic
variant matches on embedding similarity using a caller-injected embedding
function (no backend baked in). Where a provider exposes native prompt caching,
:class:`~pirn_agents.caching.prompt_cache_passthrough.PromptCachePassthrough`
defers to it instead of duplicating the work locally.
"""

__all__: list[str] = []
