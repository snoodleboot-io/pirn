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
├── cron.py       CronTrigger      — yield RunRequests on a time-based schedule
├── http.py       WebhookTrigger   — Starlette ASGI app; yield one RunRequest per POST
├── kafka.py      KafkaTrigger     — Kafka consumer; yield one RunRequest per message
└── valkey.py     ValKeyTrigger    — Valkey/Redis pub-sub; yield one RunRequest per message
```

`pirn/triggers/__init__.py` deliberately re-exports nothing — the house convention forbids import forwarding, and `scripts/check_no_import_forwarding.py` enforces it in CI. Always import from the concrete module: `from pirn.triggers.base import run_forever`, **not** `from pirn.triggers import run_forever`.

---

## Canonical pattern

### Cron-triggered pipeline

```python
import asyncio
from pirn.tapestry import Tapestry
from pirn.triggers.cron import CronTrigger
from pirn.triggers.base import run_forever

with Tapestry() as t:
    ...  # build pipeline

trigger = CronTrigger(every_seconds=3600)   # every hour, first fire immediate

async def main():
    await run_forever(trigger, t)

asyncio.run(main())
```

`CronTrigger` takes exactly one of three mutually exclusive schedule arguments:

```python
from datetime import time

CronTrigger(every_seconds=300)                      # every 5 minutes; fires at t=0 first
CronTrigger(at_times=[time(9, 0), time(17, 0)])     # daily at 09:00 and 17:00 UTC
CronTrigger(delay_fn=lambda ordinal: 60.0)          # caller-supplied per-fire delay
```

`delay_fn` is the cron seam: it maps the next 1-based fire ordinal to the seconds to wait before that fire, so a croniter/APScheduler-derived "seconds until the next cron instant" function drops straight in without pirn importing a scheduler.

Optional arguments, valid in all three modes:

```python
CronTrigger(
    every_seconds=300,
    parameters_factory=lambda: {"run_at": datetime.now(UTC).isoformat()},
    max_runs=10,        # stop after 10 requests; must be an int >= 1
    sleep=fake_sleep,   # inject the async sleep so tests advance with no wall-clock wait
)
```

### Webhook-triggered pipeline

`WebhookTrigger` does **not** bind a socket — it exposes a Starlette ASGI app as `trigger.app` for you to mount. There is no `host=` or `port=` argument; hosting decisions (TLS, CORS, which server) belong to the deployment.

```python
import uvicorn
from pirn.triggers.http import WebhookTrigger

trigger = WebhookTrigger(path="/run", auth_token=os.environ["PIRN_WEBHOOK_TOKEN"])
uvicorn.run(trigger.app, host="0.0.0.0", port=8080)
# POST to http://host:8080/run with JSON body treated as the RunRequest parameters
# Each POST yields one RunRequest
```

Also accepts `rate_limit_rpm=` (per-IP sliding-window cap, HTTP 429 on excess) and `request_builder=` (custom `(payload, request) -> RunRequest`).

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

`run_forever` is for triggers that produce independent `RunRequest` objects. For continuous data (file tail, Kafka stream), use `run_stream` from `pirn.streaming.base` instead — it handles the different lifecycle. Note it is a free function, not a `Tapestry` method.

---

## Constraints and gotchas

- **`run_forever` calls `trigger.close()` on any exit**, including cancellation. Ensure `close()` is idempotent.
- **`CronTrigger` does not backfill missed ticks.** If the process is down during a scheduled window, those runs are lost.
- **`CronTrigger(every_seconds=...)` fires immediately at t=0**, then once per interval. Use `delay_fn` if you need the first fire delayed too.
- **`CronTrigger.close()` takes effect after the in-flight sleep** and does not emit a further request.
- **`KafkaTrigger` requires `pirn[kafka]`.** It is not included in the base install.
- **`WebhookTrigger` does not run a server.** It exposes `trigger.app`; you mount it on uvicorn/hypercorn or compose it into an existing Starlette/FastAPI app, in a task alongside the rest of your async application.
- **`ValKeyTrigger` requires a Valkey/Redis connection.** Pass a configured async client at construction.
- **Nothing is exported from `pirn.triggers`.** Import from the concrete module (`pirn.triggers.base`, `pirn.triggers.cron`, …).

---

## Quick reference

| Task | How |
|------|-----|
| Run every 5 minutes | `CronTrigger(every_seconds=300)` |
| Run at fixed times of day (UTC) | `CronTrigger(at_times=[time(9, 0)])` |
| Run on an external cron backend | `CronTrigger(delay_fn=seconds_until_next_instant)` |
| Bound the number of runs | `CronTrigger(every_seconds=300, max_runs=10)` |
| Test a schedule without waiting | `CronTrigger(every_seconds=300, sleep=fake_sleep)` |
| Run on HTTP POST | `WebhookTrigger(path=...)`, then serve `trigger.app` |
| Run on Kafka message | `KafkaTrigger(topic=..., consumer=...)` |
| Run on Valkey pub-sub | `ValKeyTrigger(channel=..., client=...)` |
| Drive the trigger | `await run_forever(trigger, tapestry)` |
| Observe results | `await run_forever(trigger, tapestry, on_result=fn)` |
| Handle errors without stopping | `await run_forever(trigger, tapestry, on_error=fn)` |
| Cancel gracefully | cancel the task wrapping `run_forever`; `trigger.close()` is called automatically |

---

*See also: [pirn AGENTIC_USE.md](../../AGENTIC_USE.md)*
