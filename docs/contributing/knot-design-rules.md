# Knot Design Rules

This document defines the canonical rules for implementing a `Knot` (or `SubTapestry`) in
pirn. Every domain knot — regardless of tier, domain, or engine — must follow all rules
here. Violations are not style issues; they break the compositional contract that makes
tapestries testable, inspectable, and safe.

---

## Rule 1 — `__init__` is the wiring layer: it takes Knots

The constructor's job is to declare what the Knot depends on and hand everything to the
framework via `super().__init__(**kwargs)`. Its parameters are **Knot-typed**, not
value-typed.

There are two shapes for a non-`_config` input:

**Shape A — Known Knot type.** When the upstream is always a specific Knot kind, use that
Knot class as the hint. This documents the expected contract clearly and allows static
analysis to catch mismatches.

```python
def __init__(
    self,
    *,
    batch: DataBatchToDatafusion,
    _config: KnotConfig,
    **kwargs: Any,
) -> None:
    super().__init__(batch=batch, _config=_config, **kwargs)
```

**Shape B — `Knot | scalar_type`.** When the input may come from an upstream Knot *or*
be supplied directly as a plain scalar at pipeline-build time, annotate the union. The
framework auto-coerces the scalar into a `Parameter` node so it participates in the graph
with full lineage.

```python
def __init__(
    self,
    *,
    batch: DataBatchToDatafusion,
    how: Knot | str,
    _config: KnotConfig,
    **kwargs: Any,
) -> None:
    super().__init__(batch=batch, how=how, _config=_config, **kwargs)
```

`__init__` does nothing else. No validation, no assignment to `self._x`, no logic.

**Fan-in wiring.** A variadic input (a sequence of Knots) or a scalar that must
participate in the graph may be wired through a core fan-in node constructed in
`__init__` and passed to `super().__init__` — `Aggregator`, `Reduce`, `Parameter`,
or a map marker. That is still wiring, not logic: the node carries its own lineage
and `process()` receives the resolved value (Rule 2). Nothing else may happen in
`__init__`; `scripts/check_conventions.py` enforces exactly this shape.

```python
def __init__(self, *, models: Sequence[Knot], _config: KnotConfig, **kwargs: Any) -> None:
    numbered = {f"model_{i}": m for i, m in enumerate(models)}
    models_node = Aggregator(combine=EnsembleBuilder._order_models,
                             _config=KnotConfig(id=f"{_config.id}:models"), **numbered)
    super().__init__(models=models_node, _config=_config, **kwargs)
```

---

## Rule 2 — `process()` is the execution layer: it takes resolved values

`process()` receives the **values that the upstream Knots produced**, not the Knots
themselves. The framework resolves every parent before calling `process()` and passes the
results as plain keyword arguments.

The type hints on `process()` therefore differ from those on `__init__`:

| `__init__` hint | `process()` hint |
|-----------------|-----------------|
| `DataBatchToDatafusion` | `DatafusionDataBatch` |
| `DatafusionSessionContextKnot` | `df.SessionContext` |
| `Knot \| str` | `str` |
| `Knot \| timedelta` | `timedelta` |

```python
def __init__(
    self,
    *,
    left: DataBatchToDatafusion,
    right: DataBatchToDatafusion,
    how: Knot | str,
    _config: KnotConfig,
    **kwargs: Any,
) -> None:
    super().__init__(left=left, right=right, how=how, _config=_config, **kwargs)

async def process(
    self,
    left: DatafusionDataBatch,
    right: DatafusionDataBatch,
    how: str,
    **_: Any,
) -> DatafusionDataBatch:
    ...
```

Every input declared in `__init__` must appear by the same name in `process()`. The
`**_: Any` catch-all is required by the framework and must always be the last parameter.
It must never be used to receive declared inputs.

**Why `process()` must declare all inputs.** `process()` can be called as a standalone
function in tests, passing plain values directly without a tapestry or engine. If an input
is only reachable via `self._x`, that testing path is broken.

---

## Rule 3 — Validation and logic belong in `process()`, not `__init__()`

All validation of input values — range checks, mutual exclusion, identifier validation,
type coercion — belongs inside `process()` or in private helper methods called from
`process()`. `__init__` must not contain any guards beyond `super().__init__()`.

```python
# Correct — validation in process()
async def process(
    self,
    batch: DataBatch,
    column: str,
    max_age: timedelta,
    **_: Any,
) -> QualityReport:
    if not column:
        raise ValueError("FreshnessCheck: column must be a non-empty string")
    if max_age.total_seconds() <= 0:
        raise ValueError("FreshnessCheck: max_age must be positive")
    ...

# Wrong — validation in __init__()
def __init__(self, *, batch: Knot, column: str, max_age: timedelta, **kwargs: Any) -> None:
    if not column:
        raise ValueError(...)
    self._column = column          # also wrong: storing input as state
    ...
```

**Why.** Values that arrive via an upstream `Knot | T` input are not known at construction
time; they are only known when `process()` runs. Validation in `__init__` can never cover
that path. Validation in `process()` runs every execution, for every input shape.

---

## Rule 4 — No instance state for inputs; no `@property` fields

A Knot must not store its inputs as `self._x` instance attributes between construction and
execution, and must not expose them as `@property` fields. Inputs arrive in `process()` as
arguments; they do not need to live on the instance.

```python
# Wrong
def __init__(self, *, batch: Knot, column: Knot | str, **kwargs: Any) -> None:
    self._column = column          # storing input as state — wrong
    super().__init__(...)

@property
def column(self) -> str:           # exposing stored input — wrong
    return self._column
```

The only attributes a Knot may set on `self` are those beginning with `_mutable_`
(reserved for the base framework) or true **class-level constants** declared as `ClassVar`.

**Exception — opaque external resources.** Some inputs are objects the framework cannot
serialise or pass through the graph (e.g. a live session context backed by a Rust
extension). These may be held as instance state *only* in a dedicated vending Knot whose
sole purpose is to construct and return that resource (see Rule 6). Consumers of the
resource receive its value in `process()` as a resolved argument.

**Policy values that must not be knot-driven are classes, not state.** A small number of
settings are safety or governance policy, not data — fixed at pipeline-build time and never
swappable by wiring in a different upstream Knot at run time (e.g. whether a SQL-executing
agent may run mutating statements, PIR-817). Such a policy is not a constructor argument at
all: it is a `ClassVar` on distinct classes, and the pipeline author chooses the policy by
choosing the class (`SQLAgent` is read-only, `ReadWriteSQLAgent` may write; each runs its
statement through `SQLExecutor` or `ReadWriteSQLExecutor` respectively). Nothing is held on
the instance, and because the class is not an input, no upstream Knot's output can flip it.

---

## Rule 5 — SQL query builders and computed strings are private helpers

If a Knot derives strings (SQL, format strings, identifiers) from its inputs, those
derivations are private `@staticmethod` or regular methods called from `process()`. They
are never exposed as `@property` fields.

```python
# Correct
async def process(
    self,
    target_table: str,
    key_columns: tuple[str, ...],
    **_: Any,
) -> dict[str, Any]:
    insert_sql = self._build_insert_query(target_table, key_columns)
    ...

@staticmethod
def _build_insert_query(table: str, keys: tuple[str, ...]) -> str:
    cols = ", ".join(keys)
    placeholders = ", ".join(["?"] * len(keys))
    return f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"

# Wrong
@property
def insert_query(self) -> str:
    return f"INSERT INTO {self._target_table} ..."   # computed from stored state
```

---

## Rule 6 — Opaque resources need a dedicated vending Knot

When a domain requires a resource that cannot travel through the Knot graph (not
serialisable, holds live connections, backed by a native extension), a dedicated Knot must
be created whose `process()` constructs and returns that resource. Consumers declare the
vending Knot as a typed `__init__` input and receive the produced value in `process()`.

Examples of resources that require a vending Knot:

| Resource | Vending Knot |
|----------|--------------|
| `datafusion.SessionContext` | `DatafusionSessionContextKnot` |
| `DatabaseConnectionPool` | A pool-vending Knot |

The vending Knot may hold the resource as instance state (the narrow exception to Rule 4)
because its sole responsibility is to own and return it.

---

## Rule 7 — Naming: do not use `*Gate` for assessment Knots

The framework exposes a `Gate` primitive (`pirn.nodes.gate.gate.Gate`) that halts or
passes a pipeline based on a predicate. Knots that assess data and emit a `QualityReport`
are not Gates — they are checks. Name them accordingly. A check whose verdict is a plain
`bool` has a core base for the role: `Check` (`pirn.nodes.check.Check`), whose output
contract is exactly `True`/`False`, and which a `Gate` takes directly as its decision
(`Gate(input=value, check=verdict, ...)`) — no joined value and no lambda needed.

| Pattern | Correct | Wrong |
|---------|---------|-------|
| Quality assessment Knot | `RowCountCheck` | `RowCountGate` |
| Boolean verdict feeding a Gate | `class AcceptCheck(Check)` | `AcceptGate` |
| Framework halt primitive | `Gate(input=report, predicate=...)` or `Gate(input=value, check=verdict)` | — |

---

## Rule 8 — `SubTapestry` is only for Knots that run an inner pipeline

Use `SubTapestry` only when `process()` constructs and runs an inner `Tapestry` via
`self._run_inner(inner)`. If `process()` executes logic directly (SQL, API calls,
transforms) without building an inner tapestry, the class must inherit from `Knot`.

```python
# Correct use of SubTapestry
class ScorePipeline(SubTapestry):
    async def process(
        self, raw: DataBatch, threshold: float, **_: Any
    ) -> Knot:
        cleaned = CleanKnot(data=raw, _config=KnotConfig(id="clean"))
        scored  = ScoreKnot(
            data=cleaned, threshold=threshold, _config=KnotConfig(id="score")
        )
        return scored

# Wrong — no inner tapestry; should be plain Knot
class RowMergeKnot(SubTapestry):
    async def process(self, **_: Any) -> dict[str, Any]:
        rows = await self._source_pool.fetch_all(...)   # direct SQL, not a tapestry
        ...
```

---

## Rule 9 — Document the algorithm, mathematics, and references in the module docstring

Every Knot's module docstring must include three documentation sections where applicable.
All sections use **Google-style** headings (a word followed by a colon on its own line),
consistent with the project's `docstring_style: google` mkdocstrings configuration.

### Algorithm section

Describe what the Knot does step by step in enough detail that a reader can verify the
implementation without running it. Use numbered steps in plain language. Where the logic
benefits from pseudocode, use a fenced `text` block.

````python
"""``NullRateCheck`` — per-column null rate assessment.

Measures the fraction of null values in each configured column and
compares it against a caller-supplied threshold.

Algorithm:
    For each column in ``thresholds``:

    1. Iterate over all rows in the batch.
    2. Count rows where the column is absent or its value is ``None`` → ``k``.
    3. Divide by the total row count to obtain the observed null rate.
    4. Emit a passing check when ``observed_rate <= threshold``, failing otherwise.

    Empty batches always produce a null rate of ``0.0`` for every column.

    ```text
    for column, threshold in thresholds:
        k     = count(row[column] is None or missing for row in rows)
        rate  = k / N if N > 0 else 0.0
        emit QualityCheck(passed=(rate <= threshold), actual=rate)
    ```
"""
````

### Math section

If the Knot computes any quantitative expression — a ratio, statistic, distance, score,
threshold comparison — write it out explicitly using LaTeX inside a `.. math::` block.
MathJax renders these in the docs site via `pymdownx.arithmatex`.

```python
"""
Math:
    Given :math:`N` rows and :math:`k` null or absent values for a column:

    $$
    \\text{null\\_rate} = \\begin{cases}
        k \\,/\\, N & N > 0 \\\\
        0.0        & N = 0
    \\end{cases}
    $$

    $$
    \\text{passed} = \\text{null\\_rate} \\leq \\text{threshold}
    $$
"""
```

Even simple formulae belong here — they eliminate ambiguity about rounding, edge cases,
and operator precedence.

### References section

Cite any external source the implementation is derived from: library documentation, a
paper, a book, a named methodology, or a community standard. Use a labelled list format.

If the implementation chose one strategy among several viable alternatives, cite the
alternatives too and note why the chosen approach was selected. This prevents AI
contributors from silently substituting a different approach.

```python
"""
References:
    [1] Apache DataFusion Python — DataFrame.join:
        https://datafusion.apache.org/python/autoapi/datafusion/index.html
    [2] Alternative: PyArrow Table.join (chosen DataFusion here for lazy execution):
        https://arrow.apache.org/docs/python/api/tables.html
"""
```

**When to omit sections.**

- Omit `Math` when the Knot has no quantitative computation.
- Omit `References` when the implementation is entirely pirn-native with no external
  derivation. Do not invent citations. The absence of a `References` section signals
  "pirn-native" rather than "forgot to cite".

### Full example

````python
"""``NullRateCheck`` — per-column null rate assessment.

Measures the fraction of null values in each configured column and
compares it against a caller-supplied threshold. Columns absent from
``thresholds`` are not assessed.

Algorithm:
    For each column in ``thresholds``:

    1. Iterate over all rows in the batch.
    2. Count rows where the column is absent or its value is ``None`` → ``k``.
    3. Divide by the total row count to obtain the observed null rate.
    4. Emit a passing check when ``observed_rate <= threshold``.

    Empty batches always produce a null rate of ``0.0`` for every column.

    ```text
    for column, threshold in thresholds:
        k    = count(row[column] is None or missing for row in rows)
        rate = k / N if N > 0 else 0.0
        emit QualityCheck(passed=(rate <= threshold), actual=rate)
    ```

Math:
    Given :math:`N` rows and :math:`k` null or absent values for a column:

    $$
    \\text{null\\_rate} = \\begin{cases}
        k \\,/\\, N & N > 0 \\\\
        0.0        & N = 0
    \\end{cases}
    $$

    $$
    \\text{passed} = \\text{null\\_rate} \\leq \\text{threshold}
    $$

References:
    [1] Great Expectations — column null proportion expectation:
        https://docs.greatexpectations.io/
    [2] dbt — generic tests (not_null):
        https://docs.getdbt.com/docs/build/data-tests
"""
````

---

## Rule 10 — Optional-engine types go through `_annotation_imports`

A knot whose `process()` annotations name a type from an optional dependency (pandas,
Polars, DuckDB, ...) imports that dependency only under `if TYPE_CHECKING:` and declares
each annotation name in `_annotation_imports` (`AnnotationImport(module, extra=,
package=, attribute=)`). `Knot` resolves the declared imports on first construction, so
validation matches an eager import, importing the module never loads the engine, and a
missing engine raises the package's install hint at construction. Runtime use of the
engine is a plain import inside the method. Full pattern:
`docs/contributing/domain-knots.md`, "Knots whose annotations name an optional engine's
types".

---

## Rule 11 — Choose the topology before reaching for a loop

A pipeline that repeats work has three shapes available. Pick by asking two questions
about the repetition, in this order.

**1. Is the number of repetitions known when the pipeline is built?**
**2. Can any repetition be skipped?**

If the count is known *and* nothing is skipped, it is **not a loop**. Wire the knots at
build time. Then one more question decides which build-time shape:

**3. Does each repetition depend on the previous one's output?**

And when the count is *not* known at build time, one question separates the two cases
that look alike:

**4. Is the count known once the run reaches this knot, or only as the rounds go?**

| Count known | Anything skipped | Rounds depend on each other | Shape |
|---|---|---|---|
| at build time | no | yes | **Chain** — knot *n* takes knot *n−1* as an input |
| at build time | no | no | **Fan-out** — every knot wired as a parent of one `Aggregator` |
| at run time | — | no | **Run-time fan-out** — a `NestedRunKnot` building N knots in an inner run |
| only as rounds go | — | yes | **`LoopSubTapestry`** — `step` / `fold` decide as the run goes |
| at build time | yes | — | **`LoopSubTapestry`** — build only what is actually attempted |

### Chain — sequential dependence

`RoundRobinReview` passes a draft through N reviewers, each revising the last. Every
reviewer always runs and N is fixed at construction, so it is a chain:

```python
current: Knot | AgentResponse = response
for index, reviewer in enumerate(reviewer_list):
    current = ReviewerInvocation(
        reviewer=SpecialistHandle(specialist=reviewer),
        response=current,
        _config=KnotConfig(id=f"review_{index}"),
    )
return current
```

When the pipeline needs every intermediate output rather than only the last, end the
chain with an `Aggregator` over all the links — `PromptChainPipeline` does exactly this.

### Fan-out — independent repetitions

When the repetitions do not read each other's output, wire them all as parents of one
`Aggregator`. The engine starts every sibling as its own task, so they run concurrently:
see `ParallelSpecialistFanOut`. Sequencing independent work costs wall time for nothing,
and with one LLM call per item that cost is the dominant one in the pipeline.

### Run-time fan-out — N independent repetitions, N known only at run time

The row most often read wrong. "The count is not known at build time" is **not** by
itself a reason to loop: a knot that receives a list and must do one independent thing per
element knows N the moment it runs, and a loop would serialise work that has no reason to
be sequential.

The shape is a `NestedRunKnot` whose `process()` builds one knot per element in an inner
tapestry and awaits one `_run_inner`:

```python
with Tapestry() as inner:
    store_node = Parameter("store", MemoryStore, default=store, _config=KnotConfig(id="store"))
    per_fact = {
        f"fact_{index}": StoredSemanticFact(
            fact=fact, store=store_node, _config=KnotConfig(id=f"fact_{index}")
        )
        for index, fact in enumerate(facts)
    }
    Aggregator(combine=_count_keys, _config=KnotConfig(id="written"), **per_fact)
run = await self._run_inner(inner)
return run.outputs["written"]
```

`SemanticFactWriter`, `EmbeddingIndexer`, `MemoryLineageRecall` and `MapAgent`'s resume
probe are all this shape. Each repetition gets its own `Result`, retry, timeout and
lineage row, and the engine runs them together.

Two things to get right:

- **The collaborator becomes a `Parameter` node**, not a captured constant, so it is one
  graph node the siblings share.
- **Order comes from the key, not from the mapping.** The `Aggregator`'s `combine`
  receives `{"item_0": …, "item_1": …}` and must sort on the parsed index. Anything
  order-sensitive downstream — a running cap, "the first match wins", a position-addressed
  id — is otherwise decided by whichever call finished first.

That second point is where converting a sequential loop actually changes behaviour, so
check for it: `SemanticMemoryUpsert`'s dedup silently relied on turn *n*'s write being
visible to turn *n+1*'s read, which concurrency breaks. Collapse the duplicates before
building the knots instead.

### Fan-out downstream of a producer — N known only mid-round

When the elements come from a knot in the *same* round — an LLM proposes candidates, then
each candidate is scored — the fan-out cannot be declared when that round's tapestry is
built. Put a `NestedRunKnot` downstream of the producer and let it open the fan-out over
what the producer returned: `LatsChildScorer` takes the proposer's actions as an input and
scores each in an inner run. The alternative, folding the scores in `afold`, puts N
collaborator calls outside the engine again.

### Loop — the shape is unknown until the run

`LoopSubTapestry` earns its place when iterations may not happen, or when round *n+1*'s
work is decided by round *n*'s results. `CascadeLoop` stops at the first tier that
accepts, so unrolling every tier up front would schedule knots that merely pass state
through. `GraphTraversalLoop`'s next frontier is whatever the last hop discovered, and
`RaptorLevelLoop`'s next level clusters the level below it. Those are the cases a loop is
for — and note that each still fans its *within-round* work out, because a round's
per-node queries are independent of each other even though the rounds are not.

A loop's `step` and `fold` run **outside** the round's tapestry. Anything they await is
therefore invisible to the run, which makes them the favourite hiding place for the very
bypass the loop was adopted to remove: `ReflexionLoop` read its reflections in `astep` and
`LatsStepLoop` scored its children in `afold`, so a correctly-shaped loop still gave the
whole round one lineage row for N calls. If `step` or `fold` awaits a collaborator, that
call belongs in the round's tapestry as a knot.

### Why this matters beyond tidiness

A loop is not a free stylistic choice. It costs one inner run per iteration, a state
object that must be describable to the schema (so it cannot carry a `SubTapestry`), and a
`step`/`fold` pair to maintain. It also tempts the loop class into holding its
collaborators as instance state, which violates Rule 4 — `step` receives only the state,
so an input declared the Rule 1 way never reaches it.

### The false premise to watch for

Three pipelines used a loop over a sequence that was fully known up front, each citing
the same reason: "each step must be a real, individually-traceable knot". That is true and
does not imply a loop — a chain of knots wired at build time is equally traceable, and
every one of them appears in run history with its own inputs, outputs and timing. If the
only argument for a loop is traceability, the answer is a chain or a fan-out.

---

## A note on `pirn/nodes/*` and framework primitives

`pirn/nodes/` (`Gate`, `SubTapestry`, `LoopSubTapestry`, `Aggregator`, `Parameter`, …) and
`pirn/core/parameter.py` are the framework's own bootstrap primitives, not domain knots.
Several of them construct instance state directly in `__init__` (`Parameter`, for
example, bypasses the standard parent/config introspection entirely, because its
`process()` signature is framework-managed rather than user-declared) — this is what
*implements* Rules 1-7 for every other knot, so it cannot itself be written in terms of
them without a bootstrapping paradox. This is not a blanket exemption for anything under
`pirn/nodes/`: it is why `scripts/check_conventions.py`'s AST gate carries an explicit,
narrow allowlist for exactly these files (rules covering `__init__` purity, self-assigned
state, and `@property` fields), reviewed the same way any other rule exception is. New
files under `pirn/nodes/` do not inherit the allowlist automatically — extending it needs
the same documented justification as the constructor-state exception above.

The same reasoning covers the roots themselves. `Knot.__init__` is the introspection that
turns a subclass's keyword arguments into parents, `Knot.knot_id` / `config` / `parents` /
`config_values` / `input_names` are the framework's read-only accessors over its own
`_mutable_` state, and `Aggregator.process(**inputs)` is the variadic fan-in whose parent
names are given at construction rather than in a signature. The gate therefore does not
apply Rules 1, 2 (catch-all naming) and 4 to pirn-core's own definition of a root it keys
on (`Knot` in `pirn/core/knot.py`, `Aggregator` in `pirn/nodes/aggregator.py`, …); every
subclass of a root, and a same-named class anywhere else, is checked like any other knot.

---

## Summary checklist

Before opening a PR with a new or modified Knot:

- [ ] `__init__` parameters use Knot types (specific Knot class or `Knot | scalar_type`).
- [ ] `process()` parameters use the resolved value types (what each Knot produces, or `scalar_type` for `Knot | T` inputs).
- [ ] Every input in `__init__` appears by the same name in `process()`.
- [ ] `process()` ends with `**_: Any`.
- [ ] `__init__` contains only `super().__init__(...)` — no validation, no `self._x`.
- [ ] All validation lives in `process()` or helpers it calls.
- [ ] No `@property` fields exposing inputs or derived strings.
- [ ] Opaque resources are vended by a dedicated Knot.
- [ ] Assessment Knots returning `QualityReport` use `*Check` suffix, not `*Gate`.
- [ ] Classes that do not build inner tapestries inherit from `Knot`, not `SubTapestry`.
- [ ] `hashlib.md5()` calls include `usedforsecurity=False`.
- [ ] Module docstring has an `Algorithm:` section describing the steps.
- [ ] Module docstring has a `Math:` section with LaTeX formulae for any quantitative computation.
- [ ] Module docstring has a `References:` section for any externally-derived algorithm, pattern, or API; alternatives cited with rationale where multiple approaches exist.
- [ ] Optional-engine types are imported under `if TYPE_CHECKING:` and declared in `_annotation_imports` (Rule 10).
- [ ] Repeated work uses the right topology: a chain or fan-out at build time, a run-time fan-out in a `NestedRunKnot` when N is known only once the knot runs, a `LoopSubTapestry` only when rounds depend on each other or may be skipped — and nothing a loop's `step`/`fold` awaits is a collaborator (Rule 11).
