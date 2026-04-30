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

## LogEmitter

Writes structured JSON to Python `logging`.

::: pirn.emitters.log.LogEmitter
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.emitters import LogEmitter
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
from pirn.emitters import OpenTelemetryEmitter
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
from pirn.emitters import KafkaEmitter

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
from pirn.emitters import WebhookEmitter

t = Tapestry(emitters=[WebhookEmitter(url="https://hooks.slack.com/...")])
```

---

## EmitterErrorPolicy

::: pirn.emitters.emitter_error_policy.EmitterErrorPolicy
    options:
      show_source: false
      heading_level: 3
