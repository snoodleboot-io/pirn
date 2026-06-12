`pirn.connectors.streaming` provides `MessageBroker` implementations for Kafka, Kinesis, RabbitMQ, Google Pub/Sub, ValKey streams, and Azure Service Bus — it does not handle continuous tapestry ticking; use `pirn.streaming` with `KafkaStreamingSource` for that.

---

## Mental model

Each broker has a `*Config` (connection details, topic/queue name) and a `*Broker` (`MessageBroker` subclass with `publish()`, `consume()`, `close()`). Create the config, pass it to the broker constructor, then pass the broker to `MessageBrokerPublishSink` or `MessageBrokerConsumeSource` knots. Brokers are `PirnOpaqueValue` — create once, reuse across tapestries.

The key distinction from `pirn.streaming`: these brokers are used for discrete message passing inside a tapestry (publish a result, consume a trigger message). Use `pirn.streaming` when the broker is the *continuous* clock driving tapestry ticks.

---

## Source map

```
pirn/domains/connectors/streaming/
├── kafka_config.py              KafkaConfig              — bootstrap_servers, topic, group_id, security
├── kafka_broker.py              KafkaBroker              — Kafka via aiokafka
├── kinesis_config.py            KinesisConfig            — stream_name, region, credentials
├── kinesis_broker.py            KinesisBroker            — AWS Kinesis via aiobotocore
├── rabbitmq_config.py           RabbitmqConfig           — host, port, vhost, user, password, queue
├── rabbitmq_broker.py           RabbitmqBroker           — RabbitMQ via aio-pika
├── rabbitmq_plain_message.py    RabbitmqPlainMessage     — simple message wrapper for RabbitMQ
├── pubsub_config.py             PubsubConfig             — project, topic, subscription, credentials_json
├── pubsub_broker.py             PubsubBroker             — Google Pub/Sub via gcloud-aio-pubsub
├── valkey_stream_config.py      ValkeyStreamConfig       — host, port, stream_key, group
├── valkey_stream_broker.py      ValkeyStreamBroker       — ValKey/Redis streams via redis-py async
├── azure_servicebus_config.py   AzureServiceBusConfig    — connection_string, queue_name or topic_name
├── azure_servicebus_broker.py   AzureServiceBusBroker    — Azure Service Bus via azure-servicebus async
└── azure_servicebus_stub_message.py  AzureServiceBusStubMessage — message wrapper for Service Bus
```

---

## Canonical pattern

### Publish a result to Kafka

```python
from pirn.connectors.streaming.kafka_config import KafkaConfig
from pirn.connectors.streaming.kafka_broker import KafkaBroker
from pirn.connectors.knots.message_broker_publish_sink import MessageBrokerPublishSink
from pirn import Tapestry, KnotConfig, RunRequest

broker = KafkaBroker(config=KafkaConfig(
    bootstrap_servers="broker:9092",
    topic="pipeline-results",
))

with Tapestry() as t:
    result  = ProcessKnot(_config=KnotConfig(id="process"))
    MessageBrokerPublishSink(broker=broker, message=result, _config=KnotConfig(id="publish"))

result = await t.run(RunRequest())
await broker.close()
```

### Consume a single message as tapestry input

```python
from pirn.connectors.knots.message_broker_consume_source import MessageBrokerConsumeSource

with Tapestry() as t:
    msg = MessageBrokerConsumeSource(broker=broker, _config=KnotConfig(id="consume"))
    ProcessKnot(message=msg, _config=KnotConfig(id="process"))
```

---

## Anti-patterns

**Using `MessageBrokerConsumeSource` as a continuous driver** — this knot consumes one message per tapestry run. For continuous consumption, use `pirn.streaming.KafkaStreamingSource` with `run_stream()`.

**Creating a new broker per run** — brokers hold open connections and consumer group state. Creating inside the `with Tapestry()` block reconnects on every run and loses consumer offset tracking.

---

## Constraints and gotchas

- **Each broker requires its own extra:** `pirn[kafka]`, `pirn[kinesis]`, `pirn[rabbitmq]`, `pirn[pubsub]`, `pirn[valkey]`, `pirn[azure-servicebus]`.
- **`KafkaBroker` with `group_id` enables consumer group offset tracking.** Without it, consume starts at the latest offset.
- **`ValkeyStreamBroker` uses Redis Streams XADD/XREAD semantics.** The `group` field enables consumer group mode; omit it for simple XREAD without acknowledgement.
- **`RabbitmqBroker.consume()` returns a single message and acks it.** For batched consumption, call in a loop or use `pirn.streaming`.

---

## Quick reference

| Task | How |
|------|-----|
| Publish result to Kafka | `MessageBrokerPublishSink(broker=KafkaBroker(...), message=...)` |
| Consume from Kafka | `MessageBrokerConsumeSource(broker=KafkaBroker(...))` |
| Publish to RabbitMQ | `MessageBrokerPublishSink(broker=RabbitmqBroker(...), message=...)` |
| Publish to Kinesis | `MessageBrokerPublishSink(broker=KinesisBroker(...), message=...)` |
| Publish to Pub/Sub | `MessageBrokerPublishSink(broker=PubsubBroker(...), message=...)` |
| Stream continuously from Kafka | use `pirn.streaming.KafkaStreamingSource` |

---

*See also: [connectors AGENTIC_USE.md](../AGENTIC_USE.md)*
