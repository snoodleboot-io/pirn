# Streaming Sources

Streaming sources feed continuous data into a long-running pipeline — ETL-style. Each element from the source becomes one run, with the element bound to a named parameter.

---

## When to use streaming vs triggers

| | Streaming (`run_stream`) | Trigger (`run_forever`) |
|-|--------------------------|------------------------|
| Input shape | One value per tick | Full `RunRequest` per event |
| Extra params | Constant across all ticks | Specified per event |
| Use case | ETL, log processing, sensor data | Webhooks, Kafka events with complex routing |

---

## IterableSource

Wrap any Python iterable — lists, generators, range objects:

```python
import asyncio
from pirn import Tapestry, Parameter, KnotConfig, knot, RunRequest
from pirn.streaming import IterableSource, run_stream


@knot
async def process_record(record: dict) -> dict:
    return {**record, "processed": True, "score": record.get("value", 0) * 2}


async def handle_result(value, result):
    print(f"  Input: {value} → Output: {result.outputs.get('process_record')}")


async def main():
    records = [
        {"id": 1, "value": 10},
        {"id": 2, "value": 20},
        {"id": 3, "value": 30},
    ]

    with Tapestry() as t:
        record = Parameter("record", dict)
        processed = process_record(
            record=record,
            _config=KnotConfig(id="process_record"),
        )

    source = IterableSource(
        items=records,
        parameter_name="record",   # must match the Parameter id
    )

    await run_stream(source, t, on_result=handle_result)


asyncio.run(main())
```

Output:

```
  Input: {'id': 1, 'value': 10} → Output: {'id': 1, 'value': 10, 'processed': True, 'score': 20}
  Input: {'id': 2, 'value': 20} → Output: {'id': 2, 'value': 20, 'processed': True, 'score': 40}
  Input: {'id': 3, 'value': 30} → Output: {'id': 3, 'value': 30, 'processed': True, 'score': 60}
```

---

## FileTailSource

Tail a log file and process each new line as it arrives:

```python
from pirn.streaming import FileTailSource


@knot
async def parse_log_line(line: str) -> dict | None:
    """Parse a structured log line."""
    parts = line.strip().split(" ", 3)
    if len(parts) < 4:
        return None
    level, timestamp, service, message = parts
    return {"level": level, "service": service, "message": message}


async def main():
    with Tapestry() as t:
        line = Parameter("line", str)
        parsed = parse_log_line(
            line=line,
            _config=KnotConfig(id="parse_log_line"),
        )

    source = FileTailSource(
        path="/var/log/app.log",
        parameter_name="line",
    )

    # Runs until cancelled or the file disappears
    await run_stream(source, t)


asyncio.run(main())
```

`FileTailSource` starts at the current end of file and follows new content. It does not replay historical content.

---

## KafkaStreamingSource

Consume a Kafka topic, one run per message:

```python
from pirn.streaming import KafkaStreamingSource


@knot
async def enrich_event(event: dict) -> dict:
    return {**event, "enriched": True}


async def main():
    with Tapestry() as t:
        event = Parameter("event", dict)
        enriched = enrich_event(
            event=event,
            _config=KnotConfig(id="enriched"),
        )

    source = KafkaStreamingSource(
        topic="raw-events",
        bootstrap_servers="kafka:9092",
        group_id="pirn-enricher",
        parameter_name="event",
    )

    await run_stream(
        source,
        t,
        on_result=lambda val, res: print(res.outputs["enriched"]),
        on_error=lambda val, exc: print(f"Error: {exc}"),
    )


asyncio.run(main())
```

---

## Extra parameters in streaming

Pass constant values shared across all streaming ticks with `extra_parameters`:

```python
from pirn.streaming.base import run_stream

await run_stream(
    source,
    tapestry,
    extra_parameters={
        "model_version": "v2",
        "threshold": 0.8,
    },
)
```

These are merged into the `RunRequest.parameters` for every tick. Parameters in `extra_parameters` must correspond to `Parameter` knots in the tapestry.

---

## Using a streaming source as a trigger

Adapt a streaming source to the `Trigger` protocol with `StreamingSourceTrigger`:

```python
from pirn.streaming import FileTailSource, StreamingSourceTrigger
from pirn.triggers import run_forever

source = FileTailSource("/var/log/app.log", parameter_name="line")
trigger = StreamingSourceTrigger(source)

await run_forever(trigger, tapestry, on_result=handle_result)
```

This is useful when you want to use trigger-aware infrastructure (emitters, cancellation, backpressure) with a streaming source.

---

## Error handling in streams

`on_error` receives the raw source value and the exception:

```python
async def handle_error(value, exc: Exception) -> None:
    print(f"Failed to process {value!r}: {exc}")
    # Log, alert, or push to a dead-letter queue

await run_stream(source, tapestry, on_error=handle_error)
```

If `on_error` is not provided, exceptions from individual runs are logged and the stream continues.

---

## Graceful shutdown

`run_stream` calls `source.close()` in its `finally` block — on normal completion, cancellation, or error:

```python
import asyncio

task = asyncio.create_task(run_stream(source, tapestry))

# Shut down gracefully after 60 seconds
await asyncio.sleep(60)
task.cancel()
try:
    await task
except asyncio.CancelledError:
    pass
# source.close() has already been called
```

---

**See also:** [API — Streaming](../api/streaming.md), [Triggers](../api/triggers.md)
