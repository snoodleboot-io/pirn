`pirn.streaming` drives continuous data sources against a tapestry — one run per emitted value — it does not handle discrete external events or build `RunRequest` objects from scratch; use `pirn.triggers` for those.

---

## Mental model

A `StreamingSource` is an async generator that yields values over time. The `run_stream(source, tapestry)` driver binds each value to the parameter named `source.parameter_name` and calls `tapestry.run()` for that tick. The driver exits when the source is exhausted or when cancelled.

The critical difference from `pirn.triggers`: a `StreamingSource` is the *primary* input of the tapestry — it provides one parameter value per tick. A `Trigger` produces a complete, independent `RunRequest` per event. Use streaming when the data is continuous and the tapestry is shaped around one changing input; use triggers when each event is its own independent job.

---

## Source map

```
pirn/streaming/
├── base.py              StreamingSource       — base class; implement name, parameter_name, stream(), close()
│                        run_stream()          — driver: tick tapestry once per yielded value
├── iterable.py          IterableSource        — wrap any async iterable as a streaming source
├── file_tail.py         FileTailSource        — tail a file line-by-line as it grows
├── kafka.py             KafkaStreamingSource  — consume a Kafka topic as a continuous value stream
└── trigger_adapter.py   StreamingSourceTrigger — adapt a StreamingSource into a Trigger for run_forever
```

---

## Canonical pattern

### Kafka stream — score each message

```python
import asyncio
from pirn import Tapestry, Parameter, KnotConfig
from pirn.streaming.kafka import KafkaStreamingSource
from pirn.streaming.base import run_stream

source = KafkaStreamingSource(
    topic="raw-events",
    consumer=my_kafka_consumer,
    parameter_name="event",
)

with Tapestry() as t:
    event  = Parameter("event", dict)
    scored = ScoreKnot(event=event, _config=KnotConfig(id="score"))
    Sink(data=scored, _config=KnotConfig(id="sink"))

async def main():
    await run_stream(source, t, on_result=lambda v, r: print(r.outputs["score"]))

asyncio.run(main())
```

### File tail — process each new line

```python
from pirn.streaming.file_tail import FileTailSource

source = FileTailSource(path="/var/log/app.log", parameter_name="line")
# Yields each new line appended to the file
```

### Wrap an async iterable

```python
from pirn.streaming.iterable import IterableSource

async def generate():
    for i in range(100):
        yield {"id": i, "value": i * 2}

source = IterableSource(iterable=generate(), parameter_name="record")
```

### Pass constant parameters alongside the streaming value

```python
await run_stream(
    source, t,
    extra_parameters={"threshold": 0.8, "model_version": "v3"},
)
```

---

## Anti-patterns

### Using `run_stream` where `run_forever` is correct

If each event should be an independent job with its own full `RunRequest` (different parameters per event, not just one changing value), use a `Trigger` with `run_forever`. `run_stream` is for when one value from the source is *the* input and everything else is constant.

### Not exhausting the source before closing

`run_stream` calls `source.close()` on any exit, including cancellation. If you wrap the source in a context manager elsewhere, ensure `close()` is idempotent — it will be called once by `run_stream` regardless.

### Assuming `FileTailSource` handles log rotation

`FileTailSource` tails a fixed path. It does not detect rotation (rename/truncate). For production log tailing, use a dedicated log shipping agent or `KafkaStreamingSource` downstream of a log collector.

---

## Constraints and gotchas

- **`run_stream` vs `tapestry.run`**: never call `tapestry.run()` directly inside a streaming loop — `run_stream` handles request construction, error isolation, and `source.close()`.
- **`KafkaStreamingSource` requires `pirn[kafka]`.**
- **`IterableSource` exhausts once.** After the underlying iterable is consumed, the driver exits. Wrap in an infinite generator if you need a perpetual source.
- **`StreamingSourceTrigger` adapts a `StreamingSource` for use with `run_forever`** — useful if you have infrastructure that expects a `Trigger` but your data source is a `StreamingSource`.

---

## Quick reference

| Task | How |
|------|-----|
| Tick tapestry on each stream value | `await run_stream(source, tapestry)` |
| Stream from Kafka topic | `KafkaStreamingSource(topic=..., consumer=..., parameter_name=...)` |
| Stream from a file tail | `FileTailSource(path=..., parameter_name=...)` |
| Stream from any async iterable | `IterableSource(iterable=gen(), parameter_name=...)` |
| Pass constants alongside stream values | `run_stream(..., extra_parameters={"k": v})` |
| Observe per-tick results | `run_stream(..., on_result=async_fn)` |
| Use a StreamingSource with run_forever | `StreamingSourceTrigger(source=...)` |

---

*See also: [pirn AGENTIC_USE.md](../../AGENTIC_USE.md)*
