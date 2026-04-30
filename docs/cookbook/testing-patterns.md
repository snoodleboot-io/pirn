# Testing Patterns

Common patterns for testing pirn pipelines, from simple unit tests to full integration suites.

---

## Pattern 1: Test the knot function directly

`@knot`-decorated functions expose the original function as `.fn`:

```python
# myapp/knots.py
from pirn import knot

@knot
async def compute_discount(base_price: float, tier: str) -> float:
    rates = {"standard": 0.0, "premium": 0.1, "enterprise": 0.25}
    return base_price * (1 - rates.get(tier, 0.0))
```

```python
# tests/test_knots.py
import pytest

@pytest.mark.asyncio
async def test_compute_discount_standard():
    result = await compute_discount.fn(100.0, "standard")
    assert result == 100.0

@pytest.mark.asyncio
async def test_compute_discount_premium():
    result = await compute_discount.fn(100.0, "premium")
    assert result == pytest.approx(90.0)

@pytest.mark.asyncio
async def test_compute_discount_unknown_tier():
    result = await compute_discount.fn(100.0, "unknown")
    assert result == 100.0   # defaults to 0% discount
```

---

## Pattern 2: Integration test with in-memory backends

```python
import pytest
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from myapp.knots import compute_discount

@pytest.mark.asyncio
async def test_discount_pipeline():
    with Tapestry() as t:
        base = Parameter("base_price", float)
        tier = Parameter("tier", str, default="standard")
        discount = compute_discount(
            base_price=base,
            tier=tier,
            _config=KnotConfig(id="discount"),
        )

    result = await t.run(RunRequest(parameters={
        "base_price": 200.0,
        "tier": "premium",
    }))

    assert result.succeeded
    assert result.outputs["discount"] == pytest.approx(180.0)
```

---

## Pattern 3: Assert on lineage records

```python
@pytest.mark.asyncio
async def test_lineage_is_complete():
    with Tapestry() as t:
        price = Parameter("base_price", float)
        discount = compute_discount(
            base_price=price,
            tier="enterprise",
            _config=KnotConfig(id="discount"),
        )

    result = await t.run(RunRequest(parameters={"base_price": 400.0}))

    lineage = {rec.knot_id: rec for rec in result.lineage}

    assert lineage["discount"].outcome == "ok"
    assert lineage["discount"].output_hash.startswith("sha256:")
    assert "base_price" in lineage["discount"].parent_input_hashes
    assert lineage["discount"].started_at < lineage["discount"].finished_at
```

---

## Pattern 4: Test error propagation

```python
from pirn import knot, KnotConfig, ErrorPolicy

@knot
async def divide(numerator: float, denominator: float) -> float:
    return numerator / denominator  # raises ZeroDivisionError when denominator=0

@knot
async def format_result(value: float) -> str:
    return f"Result: {value:.2f}"

@pytest.mark.asyncio
async def test_division_by_zero_skips_downstream():
    with Tapestry() as t:
        n = Parameter("n", float)
        d = Parameter("d", float)
        quotient = divide(numerator=n, denominator=d, _config=KnotConfig(id="quotient"))
        formatted = format_result(value=quotient, _config=KnotConfig(id="formatted"))

    result = await t.run(RunRequest(parameters={"n": 10.0, "d": 0.0}))

    assert not result.succeeded
    lineage = {rec.knot_id: rec for rec in result.lineage}
    assert lineage["quotient"].outcome == "err"
    assert lineage["formatted"].outcome == "skipped"

    # Inspect the exception record
    err_id = lineage["quotient"].error_record_id
    exc_rec = result.exceptions[err_id]
    assert exc_rec.exc_type == "ZeroDivisionError"
```

---

## Pattern 5: Test with RECEIVE_ERRORS policy

```python
from pirn import Knot, KnotConfig, ErrorPolicy
from pirn.core.result import Result

class FallbackTotal(Knot):
    async def process(
        self,
        primary: Result[float],
        fallback: Result[float],
    ) -> float:
        if primary.is_ok:
            return primary.value
        if fallback.is_ok:
            return fallback.value
        return 0.0

@pytest.mark.asyncio
async def test_fallback_on_error():
    @knot
    async def always_errors(x: float) -> float:
        raise ValueError("primary failed")

    @knot
    async def always_works(x: float) -> float:
        return x * 0.5

    with Tapestry() as t:
        x = Parameter("x", float)
        primary = always_errors(x=x, _config=KnotConfig(id="primary"))
        fallback = always_works(x=x, _config=KnotConfig(id="fallback"))
        total = FallbackTotal(
            primary=primary,
            fallback=fallback,
            _config=KnotConfig(
                id="total",
                error_policy=ErrorPolicy.RECEIVE_ERRORS,
            ),
        )

    result = await t.run(RunRequest(parameters={"x": 10.0}))

    # total should use fallback
    assert result.outputs["total"] == 5.0
    lineage = {rec.knot_id: rec for rec in result.lineage}
    assert lineage["total"].outcome == "ok"
```

---

## Pattern 6: Test a recording emitter

```python
from pirn.emitters.base import Emitter
from pirn.core.lineage import KnotLineage
from pirn import EmitterErrorPolicy

class RecordingEmitter(Emitter):
    def __init__(self):
        self.lineage: list[KnotLineage] = []

    async def on_lineage(self, record: KnotLineage) -> None:
        self.lineage.append(record)

@pytest.mark.asyncio
async def test_emitter_receives_all_lineage():
    emitter = RecordingEmitter()

    with Tapestry(
        emitters=[emitter],
        emitter_error_policy=EmitterErrorPolicy.RAISE,
    ) as t:
        x = Parameter("x", float)
        d = compute_discount(base_price=x, tier="premium", _config=KnotConfig(id="d"))

    await t.run(RunRequest(parameters={"x": 100.0}))

    knot_ids = {rec.knot_id for rec in emitter.lineage}
    assert "d" in knot_ids
    assert all(rec.outcome in ("ok", "err", "skipped") for rec in emitter.lineage)
```

---

## Pattern 7: Test cross-run lineage queries

```python
from pirn.backends.in_memory import InMemoryHistory

@pytest.mark.asyncio
async def test_same_input_same_hash_across_runs():
    history = InMemoryHistory()

    with Tapestry(history=history) as t:
        x = Parameter("x", float)
        d = compute_discount(base_price=x, tier="standard", _config=KnotConfig(id="d"))

    result1 = await t.run(RunRequest(parameters={"x": 100.0}))
    result2 = await t.run(RunRequest(parameters={"x": 100.0}))

    hash1 = next(r.output_hash for r in result1.lineage if r.knot_id == "d")
    hash2 = next(r.output_hash for r in result2.lineage if r.knot_id == "d")
    assert hash1 == hash2

    # Both runs should be findable by output hash
    records = await history.query_lineage_by_output_hash(hash1)
    assert len(records) == 2
```

---

## Pattern 8: Test YAML pipelines

```python
from pirn import load_pipeline

YAML = """
name: test_yaml
nodes:
  - id: price
    type: parameter
    type_: float
  - id: discounted
    type: knot
    callable: compute_discount
    parents:
      base_price: price
    config:
      tier: premium
"""

@pytest.mark.asyncio
async def test_yaml_pipeline_integration():
    tapestry = load_pipeline(
        YAML,
        known_callables={"compute_discount": compute_discount},
    )

    result = await tapestry.run(RunRequest(parameters={"price": 200.0}))
    assert result.outputs["discounted"] == pytest.approx(180.0)
```

---

## Pytest fixtures

```python
# conftest.py
import pytest
from pirn.backends.in_memory import InMemoryStore, InMemoryHistory, InMemoryDataStore
from pirn import Tapestry


@pytest.fixture
def isolated_tapestry():
    """Fresh tapestry with isolated in-memory backends."""
    return Tapestry(
        store=InMemoryStore(),
        history=InMemoryHistory(),
        data_store=InMemoryDataStore(),
    )


@pytest.fixture
def recording_emitter():
    from tests.utils import RecordingEmitter
    return RecordingEmitter()
```

---

**See also:** [Testing Guide](../guides/testing.md), [Error Handling](../guides/error-handling.md)
