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
    batch: DatafusionDataBatchKnot,
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
    batch: DatafusionDataBatchKnot,
    how: Knot | str,
    _config: KnotConfig,
    **kwargs: Any,
) -> None:
    super().__init__(batch=batch, how=how, _config=_config, **kwargs)
```

`__init__` does nothing else. No validation, no assignment to `self._x`, no logic.

---

## Rule 2 — `process()` is the execution layer: it takes resolved values

`process()` receives the **values that the upstream Knots produced**, not the Knots
themselves. The framework resolves every parent before calling `process()` and passes the
results as plain keyword arguments.

The type hints on `process()` therefore differ from those on `__init__`:

| `__init__` hint | `process()` hint |
|-----------------|-----------------|
| `DatafusionDataBatchKnot` | `DatafusionDataBatch` |
| `DatafusionSessionContextKnot` | `df.SessionContext` |
| `Knot \| str` | `str` |
| `Knot \| timedelta` | `timedelta` |

```python
def __init__(
    self,
    *,
    left: DatafusionDataBatchKnot,
    right: DatafusionDataBatchKnot,
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
def __init__(self, *, batch: Knot, column: str, max_age: timedelta, ...) -> None:
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
def __init__(self, *, batch: Knot, column: Knot | str, ...) -> None:
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
are not Gates — they are checks. Name them accordingly:

| Pattern | Correct | Wrong |
|---------|---------|-------|
| Quality assessment Knot | `RowCountCheck` | `RowCountGate` |
| Framework halt primitive | `Gate(input=report, predicate=...)` | — |

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
class MergeUpsert(SubTapestry):
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

```python
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
```

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

```python
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
```

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
