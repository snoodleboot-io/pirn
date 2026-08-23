# Emitters

Emitters observe runs and fan events to logs, traces, metrics, message buses, or webhooks.

---

## Emitter protocol

::: pirn.emitters.base.Emitter
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## Nested runs

A `SubTapestry` executes its body as a separate inner run, and the engine fans
emitter events per run. The tapestry's emitters — and its `EmitterErrorPolicy` —
are forwarded into every inner run, at any nesting depth, so a knot inside a
`SubTapestry` body reaches the same emitters as one at the top level.

That forwarding is what keeps the two observability planes in agreement: inner
runs have always been recorded to the outer `RunHistory` (reachable via
`history.children_of(run_id)`), and before it they emitted nothing at all —
work that looked fully traced in the explorer while silently producing no
spans, metrics or log lines.

Consequences worth planning for:

- **You receive one `on_run_result` per inner run**, not one per top-level
  `tapestry.run()` call. A `LoopSubTapestry` runs one child run per turn, so a
  long conversational loop delivers one `on_run_result` per turn plus the status
  and lineage events of every knot inside it. There is no cap: emitters are
  always attached deliberately, and their intake is proportional to work the
  pipeline actually performed.
- **Inner runs are identifiable.** `RunResult.parent_run_id` is `None` only for
  the top-level run, and `RunResult.run_path` gives the full nesting path — use
  either to filter, sample, or aggregate if you need to bound intake yourself.
- **`run(emitters=[])` is honoured all the way down.** An explicit opt-out on
  the outer run leaves inner runs silent too.
- **An emitter registered on both an outer and an inner tapestry still receives
  each event once** — the two lists are merged by object identity.

---

## LogEmitter

Writes structured JSON to Python `logging`.

::: pirn.emitters.log.LogEmitter
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.emitters.log import LogEmitter
import logging

logging.basicConfig(level=logging.INFO)
t = Tapestry(emitters=[LogEmitter(with_payload=False)])
```

---

## OpenTelemetryEmitter (`pirn[otel]`)

Emits OTel spans per knot and per run.

::: pirn.emitters.otel.OpenTelemetryEmitter
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from pirn.emitters.otel import OpenTelemetryEmitter
from opentelemetry import trace

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)

t = Tapestry(emitters=[OpenTelemetryEmitter()])
```

---

## KafkaEmitter (`pirn[kafka]`)

Publishes events to Kafka topics.

::: pirn.emitters.kafka.KafkaEmitter
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.emitters.kafka import KafkaEmitter

emitter = KafkaEmitter(
    bootstrap_servers="kafka:9092",
    topic_status="pirn.status",
    topic_lineage="pirn.lineage",
    topic_result="pirn.result",
)
t = Tapestry(emitters=[emitter])
```

---

## ValKeyEmitter (`pirn[valkey]`)

Publishes events to a ValKey pub/sub channel.

::: pirn.emitters.valkey.ValKeyEmitter
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## WebhookEmitter

POSTs JSON to an HTTP endpoint on `on_run_result`.

::: pirn.emitters.webhook.WebhookEmitter
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.emitters.webhook import WebhookEmitter

t = Tapestry(emitters=[WebhookEmitter(url="https://hooks.slack.com/...")])
```

---

## EmitterErrorPolicy

::: pirn.emitters.emitter_error_policy.EmitterErrorPolicy
    options:
      show_source: false
      heading_level: 3
