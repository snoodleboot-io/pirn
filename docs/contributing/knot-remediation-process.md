# Knot Remediation Process

This document describes the step-by-step process for correcting a Knot that violates the
rules in [knot-design-rules.md](./knot-design-rules.md). Apply it file-by-file to any Knot
written before these rules were established.

---

## Step 1 — Inventory the violations

Read the file and list every violation before touching any code. For each input that
bypasses `process()`, record:

- Its name
- Its type as currently written in `__init__`
- The value type that the upstream Knot produces (what `process()` should receive)
- Whether it is currently stored as `self._x`, used in `__init__` validation, or exposed
  via `@property`

For the class itself, confirm whether `process()` calls `self._run_inner(...)`. If not and
the class inherits `SubTapestry`, it must be changed to `Knot`.

---

## Step 2 — Determine the two-layer signature

For each input, decide both sides of the signature split:

| `__init__` hint | `process()` hint | When to use |
|-----------------|-----------------|-------------|
| Specific Knot class (e.g. `DatafusionDataBatchKnot`) | The value the Knot produces (e.g. `DatafusionDataBatch`) | Upstream is always a known Knot kind |
| `Knot \| scalar_type` | `scalar_type` only | Value may be a scalar or come from upstream |
| A new vending Knot class | The opaque resource type | Input is an unserialisable resource |

The `process()` hint is always the plain value type — never a Knot type or a `Knot | T`
union.

---

## Step 3 — Create vending Knots for opaque resources first

If any input is an unserialisable resource (e.g. `DatabaseConnectionPool`,
`datafusion.SessionContext`), create the vending Knot before touching the consumer. The
vending Knot:

- Takes whatever construction arguments the resource needs as `Knot | scalar_type` inputs
  in `__init__`.
- Receives those resolved values in `process()` and constructs the resource there.
- Returns the resource as its output.

Only after the vending Knot exists should the consumer's `__init__` be updated to accept
it as a typed Knot input.

---

## Step 4 — Rewrite `__init__` as a pure wiring call

Strip `__init__` down to only the `super().__init__(**kwargs)` call, passing all inputs
through. Remove all validation, `self._x` assignments, and derived attribute construction.
Update type hints to the correct Knot-layer types. If the resulting `__init__` does nothing
but call `super()`, delete it entirely.

```python
# Before
def __init__(self, *, batch: Knot, column: str, max_age: timedelta, ...) -> None:
    if not column:
        raise ValueError(...)
    self._column = column
    self._max_age = max_age
    super().__init__(batch=batch, _config=_config, **kwargs)

# After — either this minimal form or deleted entirely
def __init__(
    self,
    *,
    batch: DataBatchKnot,
    column: Knot | str,
    max_age: Knot | timedelta,
    _config: KnotConfig,
    **kwargs: Any,
) -> None:
    super().__init__(batch=batch, column=column, max_age=max_age, _config=_config, **kwargs)
```

---

## Step 5 — Rewrite `process()` to declare all inputs with value types

Add every input as a named parameter on `process()`, using the resolved value types
identified in Step 2. Keep `**_: Any` as the final parameter.

```python
# Before
async def process(self, batch: DataBatch, **_: Any) -> QualityReport:
    column = self._column       # reads from stored state
    max_age = self._max_age

# After
async def process(
    self,
    batch: DataBatch,
    column: str,
    max_age: timedelta,
    **_: Any,
) -> QualityReport:
    ...
```

---

## Step 6 — Move validation into `process()` or private helpers

Take every guard that was in `__init__` and move it to the top of `process()`, or into a
`@staticmethod` or private method called from `process()`. Keep the same error messages
and exception types — only the location changes.

```python
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
```

---

## Step 7 — Remove `self._x` attributes and `@property` fields

Delete every `self._x = ...` that was storing an input. Delete every `@property` that
exposed stored input state.

If a `@property` built a derived value (e.g. a SQL string) from stored state, convert it
to a `@staticmethod` or private method that takes its inputs as explicit parameters.

```python
# Before
@property
def insert_query(self) -> str:
    cols = ", ".join(self._columns)
    return f"INSERT INTO {self._target_table} ({cols}) VALUES (...)"

# After
@staticmethod
def _build_insert_query(table: str, columns: tuple[str, ...]) -> str:
    cols = ", ".join(columns)
    return f"INSERT INTO {table} ({cols}) VALUES (...)"
```

---

## Step 8 — Fix inheritance if needed

If the class inherits `SubTapestry` but `process()` does not build and run an inner
`Tapestry` via `self._run_inner(...)`, change the base class to `Knot`.

```python
# Before
class MergeUpsert(SubTapestry): ...

# After
class MergeUpsert(Knot): ...
```

---

## Step 9 — Rename if needed

If the class is a quality assessment Knot (returns `QualityReport`) and its name ends in
`*Gate`, rename it to `*Check`. Update all references — imports, tests, `__init__.py`
exports, documentation — in the same commit as the rename.

```
FreshnessGate  → FreshnessCheck
NullRateGate   → NullRateCheck
RowCountGate   → RowCountCheck
```

---

## Step 10 — Add algorithm, math, and reference documentation

Enrich the module docstring with the three documentation sections described in Rule 9 of
[knot-design-rules.md](./knot-design-rules.md). All sections use Google-style headings.

### Algorithm

Describe what the Knot does step by step. Use numbered plain-language steps. Where the
logic benefits from showing the structure more concisely, follow with a fenced `text`
pseudocode block.

```python
"""
Algorithm:
    For each column in ``thresholds``:

    1. Count rows where the column is absent or its value is ``None`` → ``k``.
    2. Divide by the total row count to obtain the observed null rate.
    3. Emit a passing check when ``observed_rate <= threshold``.

    Empty batches always produce a null rate of ``0.0``.

    ```text
    for column, threshold in thresholds:
        k    = count(row[column] is None or missing for row in rows)
        rate = k / N if N > 0 else 0.0
        emit QualityCheck(passed=(rate <= threshold), actual=rate)
    ```
"""
```

### Math

Write out every quantitative expression using LaTeX inside `$$...$$` blocks. These render
via MathJax in the docs site (`pymdownx.arithmatex` is enabled). Include edge cases such
as zero denominators or empty inputs.

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

Omit this section if the Knot has no quantitative computation.

### References

Cite every external source the implementation is derived from. If the implementation chose
one approach among alternatives, cite the alternatives and explain the choice.

Questions to guide the search:

- Is this wrapping a specific library API? Cite that API's documentation page.
- Is this a named algorithm or strategy? Cite the paper, book, or specification.
- Is this a community methodology (dbt patterns, Kimball, etc.)? Cite it.
- Did the implementation choose one approach among alternatives? Cite those too.

```python
"""
References:
    [1] Apache DataFusion Python — DataFrame.aggregate:
        https://datafusion.apache.org/python/autoapi/datafusion/index.html
    [2] Alternative: PyArrow Table.group_by (chosen DataFusion for lazy execution):
        https://arrow.apache.org/docs/python/api/tables.html
"""
```

Omit this section only if the implementation is entirely pirn-native with no external
derivation. Do not invent citations.

---

## Step 11 — Update tests

Tests for the old `__init__`-based validation must be rewritten to call `process()`
directly with plain values. Because `process()` is now a regular coroutine with named
parameters, testing it requires no tapestry or engine.

```python
# Before (testing via constructor)
with pytest.raises(ValueError):
    FreshnessGate(batch=..., column="", max_age=timedelta(hours=1), ...)

# After (testing process() directly)
knot = FreshnessCheck(
    batch=upstream,
    column=col_knot,
    max_age=age_knot,
    _config=KnotConfig(id="fc"),
)
with pytest.raises(ValueError, match="non-empty"):
    await knot.process(batch=some_batch, column="", max_age=timedelta(hours=1))
```

Ensure each remediated Knot has tests covering:

| Scenario | What to test |
|----------|-------------|
| Happy path | Correct output for valid inputs |
| Validation errors | `process()` raises the right exception for each bad input value |
| Scalar input | Passing a scalar for a `Knot \| T` param wires correctly end-to-end |
| Knot input | Wiring an upstream Knot for a `Knot \| T` param resolves correctly |

---

## Step 12 — Verify

```bash
uv run ruff check <file>
uv run pyright <file>
uv run pytest tests/unit/ -x -q
```

All three must pass with no new failures before marking the file as remediated.

---

## Remediation order across the codebase

Work in this sequence to avoid broken imports mid-flight:

1. **Vending Knots first.** New `*Knot` types for opaque resources must exist before
   their consumers are updated.
2. **Renames first.** Apply `*Gate` → `*Check` renames at the start of each file's
   remediation so tests and imports can be updated in the same commit.
3. **Leaf Knots before composite Knots.** Fix Knots with no downstream dependents before
   those that depend on them, so each change can be tested in isolation.
4. **One file per commit.** Keeps diffs reviewable and bisectable.
