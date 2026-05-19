`pirn.engine.dispatchers` controls where each knot's `process()` call executes — it does not change what a knot does, only the thread, process, or remote worker it runs on.

---

## Mental model

A dispatcher implements one method: `async dispatch(knot, inputs) -> Result`. The engine calls it for every knot in topological order. Swapping the dispatcher changes the execution substrate for the entire tapestry. Pass a dispatcher to `Tapestry(dispatcher=...)`.

The default is `LocalDispatcher` — everything runs on the current event loop. The others trade off latency, throughput, setup complexity, and serialisation requirements.

---

## Source map

```
pirn/engine/dispatchers/
├── dispatcher.py          Dispatcher          — interface: name, async dispatch(knot, inputs) -> Result
├── local_dispatcher.py    LocalDispatcher     — current event loop; default; zero overhead
├── thread_dispatcher.py   ThreadDispatcher    — global ThreadPoolExecutor; good for blocking I/O knots
├── dask_dispatcher.py     DaskDispatcher      — Dask cluster; good for CPU-bound data workloads
├── ray_dispatcher.py      RayDispatcher       — Ray cluster; good for GPU/ML workloads and large fan-outs
└── celery_dispatcher.py   CeleryDispatcher    — Celery workers; good for long-running tasks with retries
```

---

## Choosing a dispatcher

| Dispatcher | Best for | Requires | Trade-off |
|---|---|---|---|
| `LocalDispatcher` | Pure async knots, fast I/O, dev/test | nothing | Single-process; blocking knots stall the event loop |
| `ThreadDispatcher` | Blocking I/O (DB calls, file I/O, sync SDKs) | nothing | Thread pool overhead; GIL limits CPU parallelism |
| `DaskDispatcher` | CPU-bound data transforms, large collections | `dask` | Cluster setup; values must be serialisable by cloudpickle |
| `RayDispatcher` | GPU/ML workloads, actor-based fan-out | `ray` | Cluster setup; object store serialisation |
| `CeleryDispatcher` | Long-running tasks, retries, distributed queues | `celery` + broker | Broker setup; knots must be registered on workers |

---

## Canonical pattern

### Thread pool for blocking I/O knots

```python
from pirn import Tapestry, RunRequest
from pirn.engine.dispatchers.thread_dispatcher import ThreadDispatcher

with Tapestry(dispatcher=ThreadDispatcher(max_workers=16)) as t:
    ...

result = await t.run(RunRequest())
```

### Dask for distributed data transforms

```python
from dask.distributed import Client
from pirn.engine.dispatchers.dask_dispatcher import DaskDispatcher

client = Client("tcp://scheduler:8786")
dispatcher = DaskDispatcher(client=client)

with Tapestry(dispatcher=dispatcher) as t:
    ...
```

### Ray for ML/GPU workloads

```python
import ray
from pirn.engine.dispatchers.ray_dispatcher import RayDispatcher

ray.init()
dispatcher = RayDispatcher()

with Tapestry(dispatcher=dispatcher) as t:
    ...
```

### Celery for long-running distributed tasks

```python
from celery import Celery
from pirn.engine.dispatchers.celery_dispatcher import CeleryDispatcher

app = Celery("pirn", broker="redis://localhost/0")
CeleryDispatcher.register_knots(app)   # call once at worker startup

dispatcher = CeleryDispatcher(app=app)
with Tapestry(dispatcher=dispatcher) as t:
    ...
```

---

## Anti-patterns

### Using `LocalDispatcher` with blocking knots

Blocking calls (synchronous DB queries, file I/O, `time.sleep`) inside `process()` stall the entire event loop when using `LocalDispatcher`. Switch to `ThreadDispatcher` or make the knot fully async.

### Assuming dispatchers share state

Each dispatcher submits work independently. Knots that write to shared in-process state (class variables, module globals) are not safe under `ThreadDispatcher`, `DaskDispatcher`, or `RayDispatcher`. Use knot outputs and lineage to pass state instead.

### Forgetting to register knots for `CeleryDispatcher`

`CeleryDispatcher` requires `CeleryDispatcher.register_knots(app)` to run on every Celery worker process at startup. Without it, workers cannot deserialise and execute knots — tasks will fail silently with a `KeyError`.

---

## Constraints and gotchas

- **All dispatchers receive serialised inputs.** Values passed between knots must be serialisable by the dispatcher's backend (cloudpickle for Dask/Ray, Celery's serialiser for Celery). `PirnOpaqueValue` subclasses are serialised by identity — safe, but opaque.
- **`ThreadDispatcher(max_workers=None)` uses the Python default** — `min(32, os.cpu_count() + 4)`. Set explicitly for predictable resource usage.
- **`DaskDispatcher` without a `client` argument** connects to a locally spawned scheduler. Pass `client=Client(...)` for production clusters.
- **`RayDispatcher` requires `ray.init()` before first use.** The dispatcher does not call `ray.init()` itself.
- **Dispatcher is tapestry-level, not knot-level.** All knots in a tapestry use the same dispatcher. To mix (e.g. most knots async, one CPU-bound), use `SubTapestry` with a different dispatcher on the inner tapestry.

---

## Quick reference

| Task | How |
|------|-----|
| Default (async, single process) | `Tapestry()` — `LocalDispatcher` is implicit |
| Blocking I/O knots | `Tapestry(dispatcher=ThreadDispatcher(max_workers=N))` |
| Dask cluster | `Tapestry(dispatcher=DaskDispatcher(client=Client(...)))` |
| Ray cluster | `Tapestry(dispatcher=RayDispatcher())` |
| Celery workers | `Tapestry(dispatcher=CeleryDispatcher(app=celery_app))` |
| Mixed dispatchers | use `SubTapestry` with a different `dispatcher=` on the inner tapestry |

---

*See also: [pirn AGENTIC_USE.md](../../../AGENTIC_USE.md)*
