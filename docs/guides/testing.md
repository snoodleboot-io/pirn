# Testing

This guide covers how to write tests for pirn pipelines at three levels: unit tests for individual knots, integration tests for full tapestries, and patterns for mock dispatchers and emitters.

---

## System prerequisites

Some optional extras wrap native libraries that must be present before `uv sync --all-extras` will succeed. If you run the full test suite locally, install these first:

```bash
# Debian / Ubuntu
sudo apt-get install -y \
  gdal-bin libgdal-dev \
  libsndfile1 \
  libbz2-dev liblzma-dev libcurl4-openssl-dev \
  ffmpeg
```

| Extra | Requires |
|-------|---------|
| `geopackage` | GDAL (`gdal-bin libgdal-dev`) |
| `signal` | libsndfile (`libsndfile1`) |
| `health` | HTSlib / compression libs (`libbz2-dev liblzma-dev libcurl4-openssl-dev`) |
| `oilgas` | libsegyio (build from source) or `libsegyio-dev` |
| `grib` | ecCodes C library (`libeccodes-dev`) |
| audio formats | ffmpeg (`ffmpeg`) |

Tests that require an uninstalled native dependency skip automatically — you will see `SKIPPED [reason: ...]` in pytest output.

---

## Philosophy

- Test knots in isolation first — their `process()` method is just an async function.
- Test tapestries with in-memory backends — no database setup required.
- Use `EmitterErrorPolicy.RAISE` in tests to catch broken emitters early.
- Assert on `lineage` records, not just `outputs` — verify the full execution trace.

---

## Unit testing a knot

A knot's `process()` method is an ordinary `async def`. Test it directly:

```python
# test_knots.py
import pytest
from myapp.knots import score_text


@pytest.mark.asyncio
async def test_score_text_clean():
    result = await score_text.fn("Hello, this is a friendly message.")
    assert result == pytest.approx(0.0, abs=0.01)


@pytest.mark.asyncio
async def test_score_text_toxic():
    result = await score_text.fn("This message contains spam and abuse.")
    assert result > 0.3
```

`@knot`-decorated functions expose their original function as `.fn`. For Knot subclasses, instantiate and call `process()` directly:

```python
from myapp.knots import EnrichUser

@pytest.mark.asyncio
async def test_enrich_user():
    knot_instance = EnrichUser.__new__(EnrichUser)  # skip __init__ / wiring
    result = await knot_instance.process(
        user_id="u123",
        lookup_table={"u123": {"name": "Alice", "tier": "premium"}},
    )
    assert result["name"] == "Alice"
```

---

## Integration testing a tapestry

Use all in-memory backends (the defaults). No database setup needed:

```python
import asyncio
import pytest
from pirn import Tapestry, Parameter, KnotConfig, knot, RunRequest


@knot
async def double(x: int) -> int:
    return x * 2


@knot
async def add(a: int, b: int) -> int:
    return a + b


@pytest.mark.asyncio
async def test_double_and_add():
    with Tapestry() as t:
        x = Parameter("x", int)
        d = double(x=x, _config=KnotConfig(id="d"))
        answer = add(a=x, b=d, _config=KnotConfig(id="answer"))

    result = await t.run(RunRequest(parameters={"x": 5}))

    assert result.succeeded
    assert result.outputs["d"] == 10
    assert result.outputs["answer"] == 15
```

### Asserting on lineage

```python
@pytest.mark.asyncio
async def test_lineage_records():
    with Tapestry() as t:
        x = Parameter("x", int)
        d = double(x=x, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest(parameters={"x": 3}))

    lineage = {rec.knot_id: rec for rec in result.lineage}
    assert lineage["d"].outcome == "ok"
    assert lineage["d"].output_hash.startswith("sha256:")
    assert "x" in lineage["d"].parent_input_hashes
```

### Testing error paths

Deliberately failing knots with `SKIP_IF_PARENT_FAILED`:

```python
@knot
async def always_fails(x: int) -> int:
    raise ValueError("intentional failure")


@knot
async def downstream(x: int) -> int:
    return x + 1


@pytest.mark.asyncio
async def test_skip_propagation():
    with Tapestry() as t:
        x = Parameter("x", int)
        failed = always_fails(x=x, _config=KnotConfig(id="failed"))
        down = downstream(x=failed, _config=KnotConfig(id="down"))

    result = await t.run(RunRequest(parameters={"x": 1}))

    assert not result.succeeded
    lineage = {rec.knot_id: rec for rec in result.lineage}
    assert lineage["failed"].outcome == "err"
    assert lineage["down"].outcome == "skipped"
    assert lineage["down"].skip_reason == "parent_failed_or_skipped"
```

---

## Testing with InMemoryStore and InMemoryHistory

For tests that need to query lineage across runs:

```python
from pirn.backends.in_memory import InMemoryStore, InMemoryHistory, InMemoryDataStore


@pytest.mark.asyncio
async def test_cross_run_lineage():
    store = InMemoryStore()
    history = InMemoryHistory()
    data = InMemoryDataStore()

    with Tapestry(store=store, history=history, data_store=data) as t:
        x = Parameter("x", int)
        d = double(x=x, _config=KnotConfig(id="d"))

    result1 = await t.run(RunRequest(parameters={"x": 5}))
    result2 = await t.run(RunRequest(parameters={"x": 5}))  # same input

    # Same value should produce the same hash
    hash1 = next(r.output_hash for r in result1.lineage if r.knot_id == "d")
    hash2 = next(r.output_hash for r in result2.lineage if r.knot_id == "d")
    assert hash1 == hash2

    # Query across runs by hash
    matching = await history.query_lineage_by_output_hash(hash1)
    assert len(matching) == 2
```

---

## Mock dispatchers

To test that dispatchers are called correctly, or to inject controlled results:

```python
from pirn.engine.dispatchers.dispatcher import Dispatcher
from pirn.core.result import Ok, Err
from pirn.core.knot import Knot
from pirn.managers.exception_record import ExceptionRecord
from collections.abc import Mapping
from datetime import datetime, UTC


class RecordingDispatcher:
    """Dispatcher that records all dispatch calls."""

    def __init__(self, inner: Dispatcher):
        self._inner = inner
        self.calls: list[tuple[str, dict]] = []

    @property
    def name(self) -> str:
        return f"Recording({self._inner.name})"

    async def dispatch(self, knot: Knot, inputs: Mapping) -> Ok | Err:
        self.calls.append((knot.knot_id, dict(inputs)))
        return await self._inner.dispatch(knot, inputs)


@pytest.mark.asyncio
async def test_dispatch_order():
    from pirn.engine.dispatchers import LocalDispatcher

    dispatcher = RecordingDispatcher(LocalDispatcher())

    with Tapestry(dispatcher=dispatcher) as t:
        x = Parameter("x", int)
        d = double(x=x, _config=KnotConfig(id="d"))
        answer = add(a=x, b=d, _config=KnotConfig(id="answer"))

    await t.run(RunRequest(parameters={"x": 2}))

    dispatched_ids = [call[0] for call in dispatcher.calls]
    assert dispatched_ids.index("d") < dispatched_ids.index("answer")
```

---

## Testing emitters

Use `EmitterErrorPolicy.RAISE` and a recording emitter to assert events:

```python
from pirn.emitters.base import Emitter
from pirn.core.lineage import KnotLineage
from pirn.core.context import RunResult
from pirn import EmitterErrorPolicy


class RecordingEmitter(Emitter):
    def __init__(self):
        self.lineage_records: list[KnotLineage] = []
        self.run_results: list[RunResult] = []

    async def on_lineage(self, record: KnotLineage) -> None:
        self.lineage_records.append(record)

    async def on_run_result(self, result: RunResult) -> None:
        self.run_results.append(result)


@pytest.mark.asyncio
async def test_emitter_receives_events():
    emitter = RecordingEmitter()

    with Tapestry(
        emitters=[emitter],
        emitter_error_policy=EmitterErrorPolicy.RAISE,
    ) as t:
        x = Parameter("x", int)
        d = double(x=x, _config=KnotConfig(id="d"))

    await t.run(RunRequest(parameters={"x": 7}))

    assert len(emitter.run_results) == 1
    assert emitter.run_results[0].succeeded

    knot_ids = {rec.knot_id for rec in emitter.lineage_records}
    assert "d" in knot_ids
```

---

## Testing YAML pipelines

```python
@pytest.mark.asyncio
async def test_yaml_pipeline():
    yaml_text = """
name: test_pipeline
nodes:
  - id: x
    type: parameter
    type_: int
  - id: doubled
    type: knot
    callable: double
    parents:
      x: x
"""

    tapestry = load_pipeline(yaml_text, known_callables={"double": double})
    result = await tapestry.run(RunRequest(parameters={"x": 4}))

    assert result.outputs["doubled"] == 8
```

---

## Pytest fixtures for common setups

```python
# conftest.py
import pytest
from pirn.backends.in_memory import InMemoryStore, InMemoryHistory, InMemoryDataStore
from pirn import Tapestry


@pytest.fixture
def fresh_tapestry():
    """A tapestry with isolated in-memory backends."""
    return Tapestry(
        store=InMemoryStore(),
        history=InMemoryHistory(),
        data_store=InMemoryDataStore(),
    )


@pytest.fixture
def recording_emitter():
    return RecordingEmitter()
```

---

**See also:** [Cookbook — Testing Patterns](../cookbook/testing-patterns.md), [Error Handling](error-handling.md)
