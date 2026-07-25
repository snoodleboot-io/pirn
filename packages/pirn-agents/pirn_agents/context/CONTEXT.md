# Context Management (PAE-F17 S3–S5)

Token-budgeted context assembly, provider-aware token counting, and context
compaction / summary memory. Backend-free: token counting defaults to a
character heuristic, and summarization / memory are caller-injected strategies.

## Provider-aware token counting (S3)

`TokenEstimator` is the common interface; each concrete estimator models one
provider's tokenization. `HeuristicTokenEstimator` (default) needs no tokenizer
backend — it estimates `ceil(len(text) / chars_per_token)`. A real encoder can
be dropped in later behind a lazy `_require`-guarded import + a flat extra
without touching callers.

`TokenCounter` wraps an estimator with a memoizing cache so repeated counting of
the same text is O(1) after the first estimate.

```python
from pirn_agents.context.heuristic_token_estimator import HeuristicTokenEstimator
from pirn_agents.context.token_counter import TokenCounter

counter = TokenCounter(estimator=HeuristicTokenEstimator(chars_per_token=4.0))
counter.count("some text")             # cold: estimator runs, result cached
counter.count("some text")             # warm: cache hit
counter.count_messages(messages)       # sums per-message + overhead
counter.cache_info()                   # {'hits': .., 'misses': .., 'size': ..}
```

Provider-awareness is expressed by constructing the estimator with a
provider-specific `chars_per_token` and `name`. No vendor is privileged.

## Token-budgeted assembly + eviction (S4)

`ContextAssembler` fits a sequence of `ContextItem`s (messages, retrieved
snippets, tool results — all uniform) under a `ContextBudget` (or an int token
ceiling), evicting non-pinned items via a pluggable `EvictionPolicy`.

```python
from pirn_agents.context.context_assembler import ContextAssembler
from pirn_agents.context.recency_eviction_policy import RecencyEvictionPolicy

result = await assembler.process(
    items=items, budget=ContextBudget(max_tokens=8000, reserved_tokens=1000),
    counter=counter, policy=RecencyEvictionPolicy(),
)
result.kept          # retained items, original order
result.evicted       # dropped items, eviction order
result.total_tokens  # kept token total
```

Policies (each overrides only `eviction_rank`; lower rank is evicted first):

* `RecencyEvictionPolicy` — drops oldest `position` first.
* `RelevanceEvictionPolicy` — drops lowest `relevance` first.
* `ImportanceEvictionPolicy` — drops lowest `priority` first.

**Pinned items (`pinned=True`) are never evicted**, even if they alone exceed
the budget. Assembly is O(n) in the fits-the-budget path and O(n log n) only
when eviction runs (a single sort of evictable items).

## Compaction / summary memory (S5)

`CompactionStrategy` is the **stable seam** F27 builds on: given a
`CompactionRequest`, it returns a `CompactionResult`. The default
`SummaryMemoryCompactor` summarizes the oldest non-pinned turns once fill
crosses a threshold.

```python
from pirn_agents.context.compaction_request import CompactionRequest
from pirn_agents.context.summary_memory_compactor import SummaryMemoryCompactor

compactor = SummaryMemoryCompactor(summarizer=summarizer, memory_store=store)
request = CompactionRequest(
    items=items, budget=budget, counter=counter,
    fill_threshold=0.8, persist_key="conversation-42",
)
result = await compactor.compact(request)
```

### Behaviour contract (what F27 can rely on)

* **Trigger** — compaction runs only when total tokens exceed
  `fill_threshold * available`. Below it the pass is a no-op
  (`result.triggered is False`, `result.retained == items`).
* **Pinned preservation** — pinned items always appear in `result.retained` and
  never in `result.evicted`. This is invariant across every strategy.
* **In-place summary** — evicted turns are summarized (oldest-first) into a
  single **pinned** `summary` item that takes the slot of the earliest evicted
  item; newer turns keep their order.
* **Lossless in intent** — evicted originals are surfaced in `result.evicted`
  and represented by `result.summary`.

### F27 memory integration

When a `memory_store` (any `pirn_agents.memory_store.MemoryStore`) and a
`persist_key` are both present, the produced summary is written via
`store.store(persist_key, {"summary": ..., "evicted_count": ...})`. F27 summary
memory reads these back and/or supplies richer `CompactionStrategy`
implementations behind the same `compact(request)` seam. Summarization itself is
provider-neutral (`Summarizer` is caller-injected; tests use a deterministic
stub).
