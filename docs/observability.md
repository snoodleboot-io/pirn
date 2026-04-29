# Observability

pirn emits structured events during every run. You can route them to logs,
traces, metrics, message queues, or webhooks by attaching **emitters**.

---

## Emitters overview

An emitter is a class that overrides one or more of:

```python
async def on_status(self, event: StatusEvent) -> None: ...
async def on_lineage(self, record: KnotLineage) -> None: ...
async def on_run_result(self, result: RunResult) -> None: ...
```

Attach emitters when constructing a `Tapestry`, or per-run:

```python
from pirn import Tapestry
from pirn.emitters import LogEmitter, OpenTelemetryEmitter

t = Tapestry(emitters=[LogEmitter(), OpenTelemetryEmitter()])

# Or disable emitters for one specific run:
result = await t.run(request, emitters=[])
```

Multiple emitters receive every event in parallel.

---

## Built-in emitters

| Class | Package | What it does |
|-------|---------|--------------|
| `LogEmitter` | core | Writes structured JSON to Python `logging` |
| `OpenTelemetryEmitter` | `pirn[otel]` | Emits OTel spans per knot and per run |
| `ValKeyEmitter` | `pirn[valkey]` | Publishes events to a ValKey pub/sub channel |
| `KafkaEmitter` | `pirn[kafka]` | Publishes events to a Kafka topic |
| `WebhookEmitter` | core | POSTs JSON payloads to an HTTP endpoint |

---

## OpenTelemetry traces

### Setup

Install the SDK:

```bash
pip install pirn[otel]
# plus an exporter, e.g.:
pip install opentelemetry-exporter-otlp
```

### Minimal working snippet

```python
import asyncio
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from pirn import Tapestry, knot, RunRequest
from pirn.emitters import OpenTelemetryEmitter

# 1. Configure the SDK once at process startup.
provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317"))
)
trace.set_tracer_provider(provider)

# 2. Attach the emitter to your tapestry.
emitter = OpenTelemetryEmitter()

@knot
async def my_knot(x: int) -> int:
    return x * 2

async def main():
    with Tapestry(emitters=[emitter]) as t:
        from pirn import Parameter, KnotConfig
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        my_knot(x=p, _config=KnotConfig(id="double"))

    result = await t.run(RunRequest(parameters={"x": 21}))

asyncio.run(main())
```

### What gets emitted

For every run, pirn emits:

- One **run span** named `run:<run_id>` that covers the full wall-clock
  duration of `t.run(...)`.
- One **knot span** named `knot:<knot_id>` per knot in the lineage, with
  start/end times matching the knot's actual execution window.

Each span carries these attributes:

| Attribute | Present on | Value |
|-----------|-----------|-------|
| `pirn.run_id` | run + knot | UUID identifying the run |
| `pirn.knot_id` | knot | The `id=` from `KnotConfig` |
| `pirn.knot_class` | knot | Fully qualified class name |
| `pirn.outcome` | knot | `"ok"`, `"err"`, or `"skipped"` |
| `pirn.dispatcher` | run + knot | Which engine dispatched this |
| `pirn.output_hash` | knot (ok only) | Content hash of the knot's output |
| `pirn.error_record_id` | knot (err only) | ID of the error record |
| `pirn.skip_reason` | knot (skipped only) | Why the knot was skipped |
| `pirn.succeeded` | run | Whether all required knots succeeded |

### Filtering in Jaeger / Tempo / Grafana

**By run:** filter on `pirn.run_id = "<uuid>"` to see every span for a
single pipeline execution.

**By knot:** filter on `pirn.knot_id = "my_step"` across all runs to build
latency histograms for that step.

**Errors only:** filter on `pirn.outcome = "err"` to see all failing knots
across all runs.

**In PromQL (via Tempo metrics-generator):**

```promql
histogram_quantile(0.99,
  rate(traces_spanmetrics_duration_milliseconds_bucket{
    span_name=~"knot:.*"
  }[5m])
)
```

### Nested spans (parent-child linking)

The `OpenTelemetryEmitter` emits each knot as an independent span with a
shared `pirn.run_id` attribute. This is enough for grouping in most UIs.

For true parent-child nesting (so knot spans appear visually nested under
the run span in a waterfall), pass a `tracer` that has already started a
parent context:

```python
from opentelemetry import trace, context

tracer = trace.get_tracer("pirn")

async def handle_request():
    with tracer.start_as_current_span("http.request") as parent:
        ctx = trace.set_span_in_context(parent)
        token = context.attach(ctx)
        try:
            emitter = OpenTelemetryEmitter(tracer=tracer)
            result = await t.run(request, emitters=[emitter])
        finally:
            context.detach(token)
```

---

## Structured logs

`LogEmitter` writes one JSON line per event to the standard Python logger
`pirn.emitters.log` at `INFO` level:

```python
from pirn.emitters import LogEmitter
import logging

logging.basicConfig(level=logging.INFO)
t = Tapestry(emitters=[LogEmitter()])
```

Example output:

```json
{"event": "lineage", "run_id": "abc…", "knot_id": "fetch_user", "outcome": "ok", "duration_ms": 12.4}
{"event": "run_result", "run_id": "abc…", "succeeded": true, "duration_ms": 87.2}
```

Pass these to your log aggregator (Loki, Splunk, CloudWatch) and query by
`knot_id` or `run_id`.

---

## Pub/sub with ValKey

`ValKeyEmitter` publishes each event as a JSON message to a ValKey channel:

```python
from pirn.emitters import ValKeyEmitter

emitter = ValKeyEmitter(url="redis://localhost:6379", channel="pirn:events")
t = Tapestry(emitters=[emitter])
```

A separate consumer can `SUBSCRIBE pirn:events` and forward events to a
metrics system, alerting layer, or audit log without coupling to the pipeline.

See `docs/subscribable-stores.md` for the same-process subscription model
(different use case: reacting to events within the same Python process).

---

## Webhooks

`WebhookEmitter` POSTs JSON to an HTTP endpoint on every `on_run_result`
call. Useful for Slack alerts, GitHub status checks, or custom dashboards:

```python
from pirn.emitters import WebhookEmitter

emitter = WebhookEmitter(url="https://hooks.slack.com/…")
t = Tapestry(emitters=[emitter])
```

---

## Writing a custom emitter

Subclass `Emitter` and override whichever methods you need:

```python
from pirn.emitters import Emitter
from pirn.core.lineage import KnotLineage
from pirn.core.context import RunResult

class PrometheusEmitter(Emitter):
    def __init__(self, registry):
        self._counter = registry.counter("pirn_knot_runs_total", ["knot_id", "outcome"])

    async def on_lineage(self, record: KnotLineage) -> None:
        self._counter.labels(
            knot_id=record.knot_id,
            outcome=record.outcome,
        ).inc()
```

`on_status` is called on every state transition (PENDING → RUNNING →
SUCCEEDED/FAILED/SKIPPED). It is fine-grained and high-frequency; prefer
`on_lineage` (called once per knot, after it completes) for metrics and
tracing.

---

## Combining emitters

Emitters compose — attach as many as you need:

```python
t = Tapestry(emitters=[
    LogEmitter(),
    OpenTelemetryEmitter(),
    WebhookEmitter(url="https://…"),
])
```

Each emitter receives the same events independently. A failure in one emitter
does not affect the others or the pipeline run itself — errors are logged and
swallowed.
