`pirn.triggers` provides sources of `RunRequest` objects that start a new pipeline run for each external event — it does not process data or transform values; the trigger only decides *when* a run starts and what parameters it carries.

---

## Mental model

A trigger is an async generator. It opens an external connection (HTTP server, Kafka consumer, cron schedule, Valkey subscription) and yields a `RunRequest` for each event. The `run_forever(trigger, tapestry)` driver consumes requests and calls `tapestry.run()` for each, then calls `trigger.close()` on exit.

Triggers produce independent, complete `RunRequest` objects per event. This is distinct from `pirn.streaming` where a single source value is inlined as a parameter into a shared tapestry each tick.

---

## Source map

```
pirn/triggers/
├── base.py       Trigger          — base class; implement name, stream(), close()
│                 run_forever()    — driver: pull requests from trigger, run tapestry, call callbacks
├── cron.py       CronTrigger      — yield RunRequests on a cron schedule
├── http.py       WebhookTrigger   — HTTP server; yield one RunRequest per POST
├── kafka.py      KafkaTrigger     — Kafka consumer; yield one RunRequest per message
└── valkey.py     ValKeyTrigger    — Valkey/Redis pub-sub; yield one RunRequest per message
```

---

## Canonical pattern

### Cron-triggered pipeline

```python
import asyncio
from pirn import Tapestry, KnotConfig
from pirn.triggers.cron import CronTrigger
from pirn.triggers.base import run_forever

with Tapestry() as t:
    ...  # build pipeline

trigger = CronTrigger(schedule="0 * * * *")   # every hour

async def main():
    await run_forever(trigger, t)

asyncio.run(main())
```

### Webhook-triggered pipeline

```python
from pirn.triggers.http import WebhookTrigger

trigger = WebhookTrigger(host="0.0.0.0", port=8080, path="/run")
# POST to http://host:8080/run with JSON body {"parameters": {...}}
# Each POST yields one RunRequest
```

### Observe results and errors

```python
async def on_result(request, result):
    print(f"run {result.run_id} succeeded={result.succeeded}")

async def on_error(request, exc):
    print(f"run failed: {exc}")

await run_forever(trigger, t, on_result=on_result, on_error=on_error)
```

### Custom trigger

```python
from pirn.triggers.base import Trigger
from pirn.core.run_request import RunRequest
from collections.abc import AsyncIterator

class DatabasePollTrigger(Trigger):
    @property
    def name(self) -> str:
        return "db-poll"

    async def stream(self) -> AsyncIterator[RunRequest]:
        while True:
            rows = await self._db.fetch_pending()
            for row in rows:
                yield RunRequest(parameters={"row_id": row["id"]})
            await asyncio.sleep(5)

    async def close(self) -> None:
        await self._db.close()
```

---

## Anti-patterns

### Exposing `WebhookTrigger` to a network without authentication

`WebhookTrigger` has no built-in auth. Any request to the endpoint starts a run. Always place an authenticating proxy (API gateway, nginx with mTLS, etc.) in front before exposing to any non-localhost network.

### Not handling `on_error` in production

If `on_error` is not provided and a run raises, `run_forever` re-raises and exits. Wrap with `on_error` in production to log failures and continue processing the next event.

### Using `run_forever` for a streaming source

`run_forever` is for triggers that produce independent `RunRequest` objects. For continuous data (file tail, Kafka stream), use `pirn.streaming.run_stream` instead — it handles the different lifecycle.

---

## Constraints and gotchas

- **`run_forever` calls `trigger.close()` on any exit**, including cancellation. Ensure `close()` is idempotent.
- **`CronTrigger` does not backfill missed ticks.** If the process is down during a scheduled window, those runs are lost.
- **`KafkaTrigger` requires `pirn[kafka]`.** It is not included in the base install.
- **`WebhookTrigger` blocks the event loop for the HTTP server.** Run it in a dedicated task alongside the rest of your async application.
- **`ValKeyTrigger` requires a Valkey/Redis connection.** Pass a configured async client at construction.

---

## Quick reference

| Task | How |
|------|-----|
| Run on a cron schedule | `CronTrigger(schedule="*/5 * * * *")` |
| Run on HTTP POST | `WebhookTrigger(host=..., port=..., path=...)` |
| Run on Kafka message | `KafkaTrigger(topic=..., consumer=...)` |
| Run on Valkey pub-sub | `ValKeyTrigger(channel=..., client=...)` |
| Drive the trigger | `await run_forever(trigger, tapestry)` |
| Observe results | `await run_forever(trigger, tapestry, on_result=fn)` |
| Handle errors without stopping | `await run_forever(trigger, tapestry, on_error=fn)` |
| Cancel gracefully | cancel the task wrapping `run_forever`; `trigger.close()` is called automatically |

---

*See also: [pirn AGENTIC_USE.md](../../AGENTIC_USE.md)*
