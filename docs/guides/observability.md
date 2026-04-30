# Observability

pirn emits structured events during every run. Route them to logs, traces, metrics, message queues, or webhooks by attaching **emitters**.

---

## Emitter protocol

An emitter implements three async hooks:

```python
class Emitter(Protocol):
    async def on_status(self, event: StatusEvent) -> None: ...
    async def on_lineage(self, record: KnotLineage) -> None: ...
    async def on_run_result(self, result: RunResult) -> None: ...
```

- `on_status` — fires on every knot state transition (PENDING → RUNNING → SUCCEEDED/FAILED/SKIPPED). High-frequency; use for real-time dashboards.
- `on_lineage` — fires once per knot after it completes. Best hook for metrics and tracing.
- `on_run_result` — fires once per run after `history.record_run()`. Best hook for alerting and webhooks.

A broken emitter never breaks a run — exceptions are swallowed and the run continues.

Attach emitters at construction or per-run:

```python
from pirn import Tapestry, LogEmitter, OpenTelemetryEmitter

# All runs
t = Tapestry(emitters=[LogEmitter(), OpenTelemetryEmitter()])

# One specific run (overrides tapestry defaults)
result = await t.run(request, emitters=[LogEmitter()])

# Disable all emitters for one run
result = await t.run(request, emitters=[])
```

---

## Built-in emitters

| Class | Package | Transport |
|-------|---------|-----------|
| `LogEmitter` | core | Python `logging` — structured JSON |
| `OpenTelemetryEmitter` | `pirn[otel]` | OTLP spans per knot and per run |
| `ValKeyEmitter` | `pirn[valkey]` | ValKey pub/sub channel |
| `KafkaEmitter` | `pirn[kafka]` | Kafka topics for status, lineage, results |
| `WebhookEmitter` | core | HTTP POST JSON payload |

---

## Structured logs

`LogEmitter` writes one JSON line per event to the `pirn.emitters.log` logger at `INFO` level:

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

Pass these to your log aggregator (Loki, Splunk, CloudWatch) and query by `knot_id` or `run_id`.

By default `LogEmitter` does not include output payloads. Enable with:

```python
LogEmitter(with_payload=True)
```

---

## OpenTelemetry traces

Install the SDK and an exporter:

```bash
pip install pirn[otel]
pip install opentelemetry-exporter-otlp
```

Configure the SDK once at process startup, then attach the emitter:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from pirn.emitters import OpenTelemetryEmitter

provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317"))
)
trace.set_tracer_provider(provider)

t = Tapestry(emitters=[OpenTelemetryEmitter()])
```

### What gets emitted

For every run:

- One **run span** named `run:<run_id>` covering the full wall-clock duration.
- One **knot span** named `knot:<knot_id>` per knot, with actual start/end times from the lineage record.

Span attributes:

| Attribute | Span | Value |
|-----------|------|-------|
| `pirn.run_id` | run + knot | UUID identifying the run |
| `pirn.knot_id` | knot | The `id=` from `KnotConfig` |
| `pirn.knot_class` | knot | Fully qualified class name |
| `pirn.outcome` | knot | `"ok"`, `"err"`, or `"skipped"` |
| `pirn.dispatcher` | run + knot | Which dispatcher ran the knot |
| `pirn.output_hash` | knot (ok) | Content hash of output |
| `pirn.error_record_id` | knot (err) | ID of the error record |
| `pirn.skip_reason` | knot (skipped) | Why the knot was skipped |
| `pirn.succeeded` | run | Whether all required knots succeeded |

### Querying in Jaeger / Grafana

Filter by run: `pirn.run_id = "<uuid>"` — see every span for one execution.

Filter by knot: `pirn.knot_id = "my_step"` — latency histogram across all runs.

Errors only: `pirn.outcome = "err"`.

PromQL via Tempo metrics-generator:

```promql
histogram_quantile(0.99,
  rate(traces_spanmetrics_duration_milliseconds_bucket{
    span_name=~"knot:.*"
  }[5m])
)
```

---

## Kafka emitter

Publish status, lineage, and result events to separate Kafka topics:

```python
from pirn.emitters import KafkaEmitter

emitter = KafkaEmitter(
    bootstrap_servers="kafka:9092",
    topic_status="pirn.status",
    topic_lineage="pirn.lineage",
    topic_result="pirn.result",
)
t = Tapestry(emitters=[emitter])
```

Requires `pip install pirn[kafka]`. Each event is a JSON-serialised Pydantic model. Connect downstream consumers (Flink, Spark, OpenSearch) to these topics for real-time observability.

---

## ValKey pub/sub emitter

```python
from pirn.emitters import ValKeyEmitter

emitter = ValKeyEmitter(url="redis://localhost:6379", channel="pirn:events")
t = Tapestry(emitters=[emitter])
```

A separate consumer subscribes to `pirn:events` and forwards events to a metrics system, alerting layer, or audit log without coupling to the pipeline process.

---

## Webhook emitter

`WebhookEmitter` POSTs JSON to an HTTP endpoint on every `on_run_result` call:

```python
from pirn.emitters import WebhookEmitter

emitter = WebhookEmitter(url="https://hooks.slack.com/...")
t = Tapestry(emitters=[emitter])
```

Useful for Slack alerts, GitHub status checks, or custom dashboards.

---

## Writing a custom emitter

Subclass `Emitter` and override whichever hooks you need:

```python
from pirn.emitters.base import Emitter
from pirn.core.lineage import KnotLineage
from pirn.core.context import RunResult

class PrometheusEmitter(Emitter):
    def __init__(self, registry):
        self._counter = registry.counter(
            "pirn_knot_runs_total",
            ["knot_id", "outcome"],
        )
        self._duration = registry.histogram(
            "pirn_knot_duration_ms",
            ["knot_id"],
        )

    async def on_lineage(self, record: KnotLineage) -> None:
        self._counter.labels(
            knot_id=record.knot_id,
            outcome=record.outcome,
        ).inc()
        if record.started_at and record.finished_at:
            ms = (record.finished_at - record.started_at).total_seconds() * 1000
            self._duration.labels(knot_id=record.knot_id).observe(ms)
```

!!! note "Choose the right hook"
    `on_status` fires on every state transition — fine-grained and high-frequency. Prefer `on_lineage` for metrics (called once per knot after completion) to avoid double-counting.

---

## Combining emitters

Multiple emitters receive the same events independently. A failure in one does not affect the others or the pipeline run:

```python
t = Tapestry(emitters=[
    LogEmitter(),
    OpenTelemetryEmitter(),
    WebhookEmitter(url="https://..."),
    PrometheusEmitter(registry),
])
```

---

**See also:** [Error Handling — EmitterErrorPolicy](error-handling.md#emitter-error-policy), [API — Emitters](../api/emitters.md), [Extension Points — Custom Emitters](../architecture/extension-points.md)
