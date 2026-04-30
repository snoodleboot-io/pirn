# Streaming

Streaming sources feed continuous data into a single long-running pipeline. Unlike triggers (which fire discrete runs), streaming sources create one parameter binding per tick.

---

## StreamingSource protocol

::: pirn.streaming.base.StreamingSource
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## `run_stream()`

::: pirn.streaming.base.run_stream
    options:
      show_source: false
      heading_level: 3

### Example

```python
from pirn.streaming import IterableSource, run_stream

source = IterableSource([1, 2, 3], parameter_name="x")
await run_stream(source, tapestry, on_result=handle)
```

`run_stream` calls `source.close()` in the `finally` block on any exit.

---

## IterableSource

Wraps any Python iterable as a streaming source.

::: pirn.streaming.iterable.IterableSource
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.streaming import IterableSource

source = IterableSource(
    items=[{"id": 1}, {"id": 2}, {"id": 3}],
    parameter_name="record",
)
await run_stream(source, tapestry)
```

---

## FileTailSource

Tails a file, yielding new lines as they appear.

::: pirn.streaming.file_tail.FileTailSource
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.streaming import FileTailSource

source = FileTailSource("/var/log/app.log", parameter_name="line")
await run_stream(source, tapestry, on_result=handle_log_line)
```

---

## KafkaStreamingSource (`pirn[kafka]`)

Consumes a Kafka topic, yielding one value per message.

::: pirn.streaming.kafka.KafkaStreamingSource
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.streaming import KafkaStreamingSource

source = KafkaStreamingSource(
    topic="events",
    bootstrap_servers="kafka:9092",
    group_id="pirn-stream",
    parameter_name="event",
)
await run_stream(source, tapestry)
```

---

## StreamingSourceTrigger

Adapts a `StreamingSource` to implement the `Trigger` protocol, so it can be driven by `run_forever`.

::: pirn.streaming.trigger_adapter.StreamingSourceTrigger
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.streaming import FileTailSource, StreamingSourceTrigger
from pirn.triggers import run_forever

source = FileTailSource("/var/log/app.log", parameter_name="line")
trigger = StreamingSourceTrigger(source)
await run_forever(trigger, tapestry)
```
