# Streaming

Streaming sources feed continuous data into a single long-running pipeline. Unlike triggers (which fire discrete runs), streaming sources create one parameter binding per tick.

---

## StreamingSource protocol

::: pirn.streaming.streaming_source.StreamingSource
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## `StreamingSource.run_stream()`

::: pirn.streaming.streaming_source.StreamingSource.run_stream
    options:
      show_source: false
      heading_level: 3

### Example

```python
from pirn.streaming.streaming_source import StreamingSource
from pirn.streaming.iterable_source import IterableSource

source = IterableSource([1, 2, 3], parameter_name="x")
await source.run_stream(tapestry, on_result=handle)
```

`StreamingSource.run_stream` calls `source.close()` in the `finally` block on any exit.

---

## IterableSource

Wraps any Python iterable as a streaming source.

::: pirn.streaming.iterable_source.IterableSource
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.streaming.iterable_source import IterableSource

source = IterableSource(
    items=[{"id": 1}, {"id": 2}, {"id": 3}],
    parameter_name="record",
)
await source.run_stream(tapestry)
```

---

## FileTailSource

Tails a file, yielding new lines as they appear.

::: pirn.streaming.file_tail_source.FileTailSource
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.streaming.file_tail_source import FileTailSource

source = FileTailSource("/var/log/app.log", parameter_name="line")
await source.run_stream(tapestry, on_result=handle_log_line)
```

---

## KafkaStreamingSource (`pirn-core[kafka]`)

Consumes a Kafka topic, yielding one value per message.

::: pirn.streaming.kafka_streaming_source.KafkaStreamingSource
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.streaming.kafka_streaming_source import KafkaStreamingSource

source = KafkaStreamingSource(
    topic="events",
    bootstrap_servers="kafka:9092",
    group_id="pirn-stream",
    parameter_name="event",
)
await source.run_stream(tapestry)
```

---

## StreamingSourceTrigger

Adapts a `StreamingSource` to implement the `Trigger` protocol, so it can be driven by `Trigger.run_forever`.

::: pirn.streaming.streaming_source_trigger.StreamingSourceTrigger
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.streaming.file_tail_source import FileTailSource
from pirn.streaming.streaming_source_trigger import StreamingSourceTrigger
from pirn.triggers.trigger import Trigger

source = FileTailSource("/var/log/app.log", parameter_name="line")
trigger = StreamingSourceTrigger(source)
await trigger.run_forever(tapestry)
```
