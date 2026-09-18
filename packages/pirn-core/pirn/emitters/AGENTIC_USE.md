`pirn.emitters` provides observers that receive events during a pipeline run — it does not affect execution, routing, or results; a broken emitter never breaks a run.

---

## Mental model

An emitter is an async observer. The engine calls its four hooks — `on_status`, `on_knot_result`, `on_lineage`, `on_run_result` — at defined points during every run. Emitters are passed to `Tapestry(emitters=[...])` and may be composed freely; all registered emitters fire for every event. Exceptions raised inside any emitter hook are caught and isolated under the tapestry's `emitter_error_policy` (`WARN` by default) — the run continues regardless unless the policy is `RAISE`.

`on_knot_result(knot_id, result, lineage)` (ADR agents-speaks-core, WS0b) is the live per-knot stream: awaited the moment a knot settles, inside the engine loop and before the knot's children start, with the full `Ok` / `Err` / `Skipped` and its lineage row. `on_lineage` sees the same row later, after the run is persisted and in the run's reported order. Use `on_knot_result` to stream each item of a fan-out out as it finishes; keep it to a hand-off (a queue put), since it is awaited in place.

---

## Source map

```
pirn/emitters/
├── emitter.py                 Emitter              — base class; override the hooks you need
├── emitter_error_policy.py    EmitterErrorPolicy   — enum: WARN, IGNORE, RAISE (default WARN)
├── log_emitter.py             LogEmitter           — stdlib logging; JSON-style extras; optional payload
├── open_telemetry_emitter.py  OpenTelemetryEmitter — OTel trace spans per knot lineage record
├── kafka_emitter.py           KafkaEmitter         — publish status/lineage events to a Kafka topic
├── webhook_emitter.py         WebhookEmitter       — POST run events to an HTTP endpoint
└── valkey_emitter.py          ValKeyEmitter        — publish events to a Valkey pub-sub channel
```

---

## Canonical pattern

### Add structured logging to every run

```python
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn.emitters.log_emitter import LogEmitter

with Tapestry(emitters=[LogEmitter()]) as t:
    ...

result = await t.run(RunRequest())
# pirn logger receives INFO records for every knot state transition and lineage record
```

### Compose multiple emitters

```python
from pirn.emitters.log_emitter import LogEmitter
from pirn.emitters.open_telemetry_emitter import OpenTelemetryEmitter

with Tapestry(emitters=[LogEmitter(), OpenTelemetryEmitter(tracer=my_tracer)]) as t:
    ...
```

### Custom emitter

```python
from pirn.emitters.emitter import Emitter
from pirn.core.knot_lineage import KnotLineage

class MetricsEmitter(Emitter):
    async def on_lineage(self, record: KnotLineage) -> None:
        elapsed_ms = (record.finished_at - record.started_at).total_seconds() * 1000
        MY_METRICS.histogram("pirn.knot.duration_ms").observe(
            elapsed_ms, tags={"knot": record.knot_id, "outcome": record.outcome}
        )
```

---

## Anti-patterns

### Raising exceptions in emitter hooks to signal failure

Emitter exceptions are caught and discarded (or logged, depending on `EmitterErrorPolicy`). Never use an emitter hook as an error-propagation channel — if the hook crashes, the run does not fail and no `Err` is produced.

### Doing heavy blocking I/O in an emitter hook

All hooks are `async` but they run on the same event loop as the pipeline. A hook that calls a blocking HTTP client or writes to a slow disk synchronously stalls every concurrent knot. Use async clients or `asyncio.to_thread`.

### Expecting emitter ordering to match knot execution order

`on_status` and `on_knot_result` are fired as knots run and settle; `on_lineage` and `on_run_result` are fired once the run has been persisted. Because knots run concurrently, `on_status` and `on_knot_result` events from different knots arrive interleaved in completion order; `on_lineage` records arrive in the run's reported (graph) order. Do not assume that the live streams arrive in topological order.

---

## Constraints and gotchas

- **`LogEmitter(with_payload=True)` is verbose.** It includes the full serialised `RunResult` or `KnotLineage` in each log record. Use only for debugging.
- **`OpenTelemetryEmitter` produces flat spans, not nested.** Each lineage record becomes an independent span linked by the `"pirn.run_id"` attribute. Nested span hierarchies require a custom sampler in your OTel provider.
- **`KafkaEmitter` and `ValKeyEmitter` require the respective extras.** Install `pip install "pirn-core[kafka]"` (aiokafka) or `pip install "pirn-core[valkey]"` (valkey-glide) before using them.
- **`WebhookEmitter` posts only the hooks you give a URL.** `url_status`, `url_lineage` and `url_result` each enable one delivery; a `None` URL disables it.
- **`EmitterErrorPolicy.RAISE` breaks runs on emitter failure.** Only use it in tests where you want to assert emitter correctness.

---

## Quick reference

| Task | How |
|------|-----|
| Structured logging | `Tapestry(emitters=[LogEmitter()])` |
| Verbose debug logging | `Tapestry(emitters=[LogEmitter(with_payload=True)])` |
| OTel tracing | `Tapestry(emitters=[OpenTelemetryEmitter(tracer=my_tracer)])` |
| Publish to Kafka | `Tapestry(emitters=[KafkaEmitter(topic=..., producer=...)])` |
| POST to webhook | `Tapestry(emitters=[WebhookEmitter(url_result=...)])` |
| Publish to Valkey | `Tapestry(emitters=[ValKeyEmitter(client=..., channel_lineage=...)])` |
| Custom emitter | subclass `Emitter`; override `on_status`, `on_knot_result`, `on_lineage`, or `on_run_result` |
| Compose emitters | `Tapestry(emitters=[emitter_a, emitter_b, ...])` |

---

*See also: [pirn AGENTIC_USE.md](../../AGENTIC_USE.md)*
