# Triggers

Triggers start a new pipeline run for each external event. Drive them with `run_forever(trigger, tapestry)`.

---

## Trigger protocol

::: pirn.triggers.base.Trigger
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## `run_forever()`

::: pirn.triggers.base.run_forever
    options:
      show_source: false
      heading_level: 3

### Example

```python
from pirn.triggers import CronTrigger, run_forever

trigger = CronTrigger(every_seconds=300)
await run_forever(trigger, tapestry, on_result=handle_result)
```

`run_forever` calls `trigger.close()` on exit (normal, cancelled, or errored).

---

## CronTrigger

Fires on a schedule.

::: pirn.triggers.cron.CronTrigger
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.triggers import CronTrigger, run_forever

# Run every five minutes
trigger = CronTrigger(every_seconds=300)
await run_forever(trigger, tapestry)
```

---

## WebhookTrigger

Fires on each HTTP POST request. `trigger.app` is a Starlette ASGI app you mount on any ASGI server.

::: pirn.triggers.http.WebhookTrigger
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.triggers import WebhookTrigger
import uvicorn

trigger = WebhookTrigger(path="/run")
# Mount behind an authenticating proxy before exposing to any network
uvicorn.run(trigger.app, host="127.0.0.1", port=8080)
```

!!! warning "No built-in authentication"
    `WebhookTrigger` has no built-in authentication. Always place an authenticating reverse proxy or middleware in front before exposing it to any network.

---

## KafkaTrigger

Fires on each Kafka message. Requires `pirn[kafka]`.

::: pirn.triggers.kafka.KafkaTrigger
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.triggers import KafkaTrigger, run_forever

trigger = KafkaTrigger(
    topic="orders",
    bootstrap_servers="kafka:9092",
    group_id="pirn-worker",
)
await run_forever(trigger, tapestry)
```

---

## ValkeyTrigger

Fires on ValKey pub/sub messages. Requires `pirn[valkey]`.

::: pirn.triggers.valkey.ValKeyTrigger
    options:
      show_source: false
      members_order: source
      heading_level: 3
