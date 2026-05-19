`pirn.emitters` provides observers that receive events during a pipeline run — it does not affect execution, routing, or results; a broken emitter never breaks a run.

---

## Mental model

An emitter is an async observer. The engine calls its three hooks — `on_status`, `on_lineage`, `on_run_result` — at defined points during every run. Emitters are passed to `Tapestry(emitters=[...])` and may be composed freely; all registered emitters fire for every event. Exceptions raised inside any emitter hook are caught and isolated — the run continues regardless.

---

## Source map

```
pirn/emitters/
├── base.py                  Emitter              — base class; override the hooks you need
│                            EmitterErrorPolicy   — enum: IGNORE, LOG, RAISE (default IGNORE)
├── log.py                   LogEmitter           — stdlib logging; JSON-style extras; optional payload
├── otel.py                  OpenTelemetryEmitter — OTel trace spans per knot lineage record
├── kafka.py                 KafkaEmitter         — publish status/lineage events to a Kafka topic
├── webhook.py               WebhookEmitter       — POST run events to an HTTP endpoint
└── valkey.py                ValKeyEmitter        — publish events to a Valkey/Redis pub-sub channel
```

---

## Canonical pattern

### Add structured logging to every run

```python
from pirn import Tapestry, RunRequest
from pirn.emitters.log import LogEmitter

with Tapestry(emitters=[LogEmitter()]) as t:
    ...

result = await t.run(RunRequest())
# pirn logger receives INFO records for every knot state transition and lineage record
```

### Compose multiple emitters

```python
from pirn.emitters.log import LogEmitter
from pirn.emitters.otel import OpenTelemetryEmitter

with Tapestry(emitters=[LogEmitter(), OpenTelemetryEmitter(tracer=my_tracer)]) as t:
    ...
```

### Custom emitter

```python
from pirn.emitters.base import Emitter
from pirn.core.lineage import KnotLineage

class MetricsEmitter(Emitter):
    async def on_lineage(self, record: KnotLineage) -> None:
        MY_METRICS.histogram("pirn.knot.duration_ms").observe(
            record.duration_ms, tags={"knot": record.knot_id, "outcome": record.outcome}
        )
```

---

## Anti-patterns

### Raising exceptions in emitter hooks to signal failure

Emitter exceptions are caught and discarded (or logged, depending on `EmitterErrorPolicy`). Never use an emitter hook as an error-propagation channel — if the hook crashes, the run does not fail and no `Err` is produced.

### Doing heavy blocking I/O in an emitter hook

All hooks are `async` but they run on the same event loop as the pipeline. A hook that calls a blocking HTTP client or writes to a slow disk synchronously stalls every concurrent knot. Use async clients or `asyncio.to_thread`.

### Expecting emitter ordering to match knot execution order

`on_status` and `on_lineage` are fired as knots complete. Because knots run concurrently, events from different knots may arrive interleaved. Do not assume that lineage records arrive in topological order.

---

## Constraints and gotchas

- **`LogEmitter(with_payload=True)` is verbose.** It includes the full serialised `RunResult` or `KnotLineage` in each log record. Use only for debugging.
- **`OpenTelemetryEmitter` produces flat spans, not nested.** Each lineage record becomes an independent span linked by `pirn.run_id`. Nested span hierarchies require a custom sampler in your OTel provider.
- **`KafkaEmitter` and `ValKeyEmitter` require the respective extras.** Install `pirn[kafka]` or ensure `valkey-glide` is present before using them.
- **`WebhookEmitter` fires on `on_run_result` only by default.** Check the constructor for `events` parameter to control which hook types POST to the endpoint.
- **`EmitterErrorPolicy.RAISE` breaks runs on emitter failure.** Only use it in tests where you want to assert emitter correctness.

---

## Quick reference

| Task | How |
|------|-----|
| Structured logging | `Tapestry(emitters=[LogEmitter()])` |
| Verbose debug logging | `Tapestry(emitters=[LogEmitter(with_payload=True)])` |
| OTel tracing | `Tapestry(emitters=[OpenTelemetryEmitter(tracer=my_tracer)])` |
| Publish to Kafka | `Tapestry(emitters=[KafkaEmitter(topic=..., producer=...)])` |
| POST to webhook | `Tapestry(emitters=[WebhookEmitter(url=...)])` |
| Publish to Valkey | `Tapestry(emitters=[ValKeyEmitter(channel=..., client=...)])` |
| Custom emitter | subclass `Emitter`; override `on_status`, `on_lineage`, or `on_run_result` |
| Compose emitters | `Tapestry(emitters=[emitter_a, emitter_b, ...])` |

---

*See also: [pirn AGENTIC_USE.md](../../AGENTIC_USE.md)*
