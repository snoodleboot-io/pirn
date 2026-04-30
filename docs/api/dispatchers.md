# Dispatchers

The dispatcher protocol and all built-in implementations.

All dispatchers implement the same two-method protocol. Switch between them at `Tapestry` construction time or per-run — no pipeline code changes required.

---

## Dispatcher protocol

::: pirn.engine.dispatchers.dispatcher.Dispatcher
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## LocalDispatcher

Runs knots in the current event loop. The default.

::: pirn.engine.dispatchers.local_dispatcher.LocalDispatcher
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## ThreadDispatcher

Offloads each knot to a global thread pool. Useful for CPU-bound or sync-heavy work that should not block the event loop.

::: pirn.engine.dispatchers.thread_dispatcher.ThreadDispatcher
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn import Tapestry
from pirn.engine.dispatchers import ThreadDispatcher

with Tapestry(dispatcher=ThreadDispatcher(max_workers=8)) as t:
    ...
```

---

## CeleryDispatcher (`pirn[celery]`)

Submits each knot through Celery for distributed execution.

::: pirn.engine.dispatchers.celery_dispatcher.CeleryDispatcher
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Setup

```python
# Worker side — in Celery worker init module
from celery import Celery
from pirn.engine.dispatchers.celery_dispatcher import register_celery_worker_task

app = Celery("pirn", broker="redis://localhost:6379/0")
app.conf.update(
    task_serializer="pickle",
    accept_content=["pickle"],
    result_serializer="pickle",
)
register_celery_worker_task(app)

# Driver side
from pirn.engine.dispatchers.celery_dispatcher import CeleryDispatcher

dispatcher = CeleryDispatcher(
    broker_url="redis://localhost:6379/0",
    backend_url="redis://localhost:6379/1",
)
with Tapestry(dispatcher=dispatcher) as t:
    ...
```

!!! warning "Celery uses pickle"
    Knots must be pickle-serializable. Classes defined at module scope serialize reliably. Lambdas in `selector`, `predicate`, or `combine` arguments require `cloudpickle` (use Dask/Ray instead) or explicit module-scope definitions.

---

## DaskDispatcher (`pirn[dask]`)

::: pirn.engine.dispatchers.dask_dispatcher.DaskDispatcher
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from dask.distributed import Client
from pirn.engine.dispatchers.dask_dispatcher import DaskDispatcher

client = Client("tcp://scheduler:8786")
dispatcher = DaskDispatcher(client=client)

with Tapestry(dispatcher=dispatcher) as t:
    ...
```

Dask uses `cloudpickle` — handles lambdas and locally-defined functions. Workers must have `pirn` importable.

---

## RayDispatcher (`pirn[ray]`)

::: pirn.engine.dispatchers.ray_dispatcher.RayDispatcher
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
import ray
from pirn.engine.dispatchers.ray_dispatcher import RayDispatcher

ray.init(address="ray://head:10001")
dispatcher = RayDispatcher()

with Tapestry(dispatcher=dispatcher) as t:
    ...
```
