`pirn.connectors.streaming` provides `MessageBroker` implementations for Kafka, Kinesis, RabbitMQ, Google Pub/Sub, ValKey streams, and Azure Service Bus — it does not handle continuous tapestry ticking; use `pirn.streaming.kafka_streaming_source.KafkaStreamingSource` for that.

---

## Mental model

Each broker has a `*Config` (connection details and credentials) and a `*Broker` (`MessageBroker` subclass with `publish(topic, value, *, key=, headers=)`, `consume(topic, *, group=)`, `close()`). The topic/queue/stream name is an argument to `publish()`/`consume()`, not a config field. Create the config, pass it to the broker constructor, vend the broker into the graph with `MessageBrokerKnot`, and wire that knot into `MessageBrokerPublishSink`. Brokers are `PirnOpaqueValue` — create once, reuse across tapestries.

The key distinction from `pirn.streaming`: these brokers are used for discrete message passing inside a tapestry (publish a result). Use `pirn.streaming` when the broker is the *continuous* clock driving tapestry ticks.

---

## Source map

```
pirn/connectors/streaming/
├── kafka_config.py              KafkaConfig              — bootstrap_servers, client_id, group_id, SASL/SSL
├── kafka_broker.py              KafkaBroker              — Kafka via aiokafka
├── kinesis_config.py            KinesisConfig            — region, endpoint_url, credentials, stream_arn
├── kinesis_broker.py            KinesisBroker            — AWS Kinesis via aioboto3
├── rabbitmq_config.py           RabbitMQConfig           — host, port, vhost, user, password, ssl
├── rabbitmq_broker.py           RabbitMQBroker           — RabbitMQ via aio-pika
├── pubsub_config.py             PubSubConfig             — project, service_account_json
├── pubsub_broker.py             PubSubBroker             — Google Pub/Sub via google-cloud-pubsub
├── valkey_stream_config.py      ValkeyStreamConfig       — host, port, password, use_tls, consumer_group
├── valkey_stream_broker.py      ValkeyStreamBroker       — ValKey streams via valkey-py async
├── valkey_record.py             ValkeyRecord             — record yielded by ValkeyStreamBroker.consume()
├── azure_servicebus_config.py   AzureServiceBusConfig    — connection_string or namespace
└── azure_servicebus_broker.py   AzureServiceBusBroker    — Azure Service Bus via azure-servicebus async
```

---

## Canonical pattern

### Publish a result to Kafka

```python
from pirn.connectors.knots.message_broker_knot import MessageBrokerKnot
from pirn.connectors.knots.message_broker_publish_sink import MessageBrokerPublishSink
from pirn.connectors.streaming.kafka_broker import KafkaBroker
from pirn.connectors.streaming.kafka_config import KafkaConfig
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

broker = KafkaBroker(KafkaConfig(bootstrap_servers="broker:9092"))

with Tapestry() as t:
    vend = MessageBrokerKnot(broker=broker, _config=KnotConfig(id="broker"))
    payload = ProcessKnot(_config=KnotConfig(id="process"))  # must produce bytes
    MessageBrokerPublishSink(
        broker=vend,
        topic="pipeline-results",
        value=payload,
        _config=KnotConfig(id="publish"),
    )

result = await t.run(RunRequest())
await broker.close()
```

### Consuming messages

There is no consume knot. `MessageBroker.consume(topic, *, group=)` is an async iterator for code that owns its own loop. To start one run per message, use a trigger (`pirn.triggers.kafka_trigger.KafkaTrigger`) with `Trigger.run_forever`; to feed a long-running pipeline continuously, use `pirn.streaming.kafka_streaming_source.KafkaStreamingSource` with `StreamingSource.run_stream()`.

---

## Anti-patterns

**Hand-rolling a consume loop around `tapestry.run`** — `async for msg in broker.consume(topic): await t.run(...)` re-implements the trigger loop. Use `KafkaTrigger` + `Trigger.run_forever` (one run per message) or `KafkaStreamingSource` + `StreamingSource.run_stream()` (continuous).

**Creating a new broker per run** — brokers hold open connections and consumer group state. Creating inside the `with Tapestry()` block reconnects on every run and loses consumer offset tracking.

---

## Constraints and gotchas

- **Each broker requires its own extra:** `pip install "pirn-core[kafka]"`, `"pirn-core[kinesis]"`, `"pirn-core[rabbitmq]"`, `"pirn-core[pubsub]"`, `"pirn-core[valkey]"`, `"pirn-core[azure-servicebus]"`.
- **`KafkaBroker.consume()` uses `group=` or, when omitted, `KafkaConfig.group_id`** for consumer-group offset tracking.
- **`ValkeyStreamBroker.consume()` reads with XREADGROUP.** A group is required: pass `group=` or set `ValkeyStreamConfig.consumer_group`.
- **`RabbitMQBroker.consume()` ignores `group`** — RabbitMQ fans out by queue, so use distinct queue names for independent consumers. Each yielded message is acked as it is processed.

---

## Quick reference

| Task | How |
|------|-----|
| Publish result to Kafka | `MessageBrokerPublishSink(broker=MessageBrokerKnot(broker=KafkaBroker(...)), topic=..., value=...)` |
| Publish to RabbitMQ / Kinesis / Pub/Sub | the same sink over `RabbitMQBroker(...)` / `KinesisBroker(...)` / `PubSubBroker(...)` |
| One run per Kafka message | `KafkaTrigger(topic=..., bootstrap_servers=...)` + `run_forever` |
| Stream continuously from Kafka | `KafkaStreamingSource(topic=..., bootstrap_servers=..., parameter_name=...)` + `run_stream` |

---

*See also: [connectors AGENTIC_USE.md](../AGENTIC_USE.md)*
