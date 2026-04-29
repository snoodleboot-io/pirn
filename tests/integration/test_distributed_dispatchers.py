"""Mock-driver tests for distributed dispatchers.

Real-cluster tests are gated by markers and live alongside these (see
``docs/real-backend-testing-plan.md``).  These tests verify the
adapter logic — that the dispatcher submits work and returns results
in the expected shape.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.knot import Knot
from pirn.core.ok import Ok
from pirn.engine.dispatchers.celery_dispatcher import CeleryDispatcher

PIRN_CELERY_TASK_NAME = CeleryDispatcher._task_name
from pirn.engine.dispatchers.dask_dispatcher import DaskDispatcher
from pirn.engine.dispatchers.ray_dispatcher import RayDispatcher

# ---------------------------------------------------- Dask fake client


class _FakeDaskFuture:
    def __init__(self, value: Any) -> None:
        self._value = value

    def __await__(self):
        async def _coro():
            return self._value

        return _coro().__await__()


class _FakeDaskClient:
    """Test fake.  ``submit`` runs the function in a worker thread so
    ``asyncio.run`` inside the worker has no enclosing loop, mimicking
    the real Dask worker-process behavior."""

    def __init__(self) -> None:
        self.submitted: list[tuple[Any, tuple, dict]] = []

    def submit(self, fn, *args, **kwargs) -> _FakeDaskFuture:
        import concurrent.futures

        self.submitted.append((fn, args, kwargs))
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(fn, *args, **kwargs)
            value = future.result()
        return _FakeDaskFuture(value)

    async def close(self) -> None:
        pass


# ---------------------------------------------------- Ray fake module


class _FakeRayObjectRef:
    def __init__(self, value: Any) -> None:
        self.value = value


class _FakeRayRemote:
    """Test fake.  ``remote`` runs the function in a worker thread to
    mimic Ray's worker-process behavior (no enclosing event loop)."""

    def __init__(self, fn) -> None:
        self._fn = fn

    def remote(self, *args, **kwargs) -> _FakeRayObjectRef:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._fn, *args, **kwargs)
            return _FakeRayObjectRef(future.result())


class _FakeRayModule:
    def __init__(self) -> None:
        self.init_calls: list[dict] = []
        self.shutdown_calls = 0

    def init(self, **kwargs: Any) -> None:
        self.init_calls.append(kwargs)

    def remote(self, fn) -> _FakeRayRemote:
        return _FakeRayRemote(fn)

    def get(self, ref: _FakeRayObjectRef) -> Any:
        return ref.value

    def shutdown(self) -> None:
        self.shutdown_calls += 1


# ---------------------------------------------------- Celery fake app


class _FakeAsyncResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def get(self) -> Any:
        return self._value


class _FakeCeleryApp:
    """Test fake.  Tasks registered via ``@app.task`` are invoked in a
    worker thread so the worker has no enclosing event loop (same as
    a real Celery worker process)."""

    def __init__(self) -> None:
        self.tasks_sent: list[tuple[str, tuple]] = []
        self.task_handlers: dict[str, Any] = {}

    def send_task(self, name: str, args: tuple) -> _FakeAsyncResult:
        import concurrent.futures

        self.tasks_sent.append((name, args))
        if name in self.task_handlers:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.task_handlers[name], *args)
                value = future.result()
            return _FakeAsyncResult(value)
        return _FakeAsyncResult(None)

    def task(self, name: str = ""):
        def decorator(fn):
            self.task_handlers[name] = fn
            return fn

        return decorator


# ---------------------------------------------------- helpers


@knot
async def _double(x: int) -> int:
    return x * 2


def _build_knot() -> Knot:
    """Build a knot we can hand to a dispatcher.

    Construct outside any Tapestry context so it doesn't accidentally
    register with one.
    """
    return _double(x=42, _config=KnotConfig(id="d", validate_io=False))


# Note: knots constructed with concrete (non-Knot) inputs treat those
# values as config; the kwarg name on process is "x", with type int, so
# 42 is valid config.


# ---------------------------------------------------- Dask tests


async def test_dask_dispatcher_name():
    d = DaskDispatcher(client=_FakeDaskClient())
    assert d.name == "DaskDispatcher"


async def test_dask_dispatcher_requires_client_or_scheduler():
    with pytest.raises(TypeError):
        DaskDispatcher()


async def test_dask_dispatcher_submits_and_returns_result():
    client = _FakeDaskClient()
    d = DaskDispatcher(client=client)
    knot = _build_knot()
    # Override the validator to skip — `42` has been bound as config so
    # the inputs Mapping is empty.
    result = await d.dispatch(knot, {})
    assert isinstance(result, Ok)
    assert result.value == 84
    # We submitted exactly one task.
    assert len(client.submitted) == 1


# ---------------------------------------------------- Ray tests


async def test_ray_dispatcher_name():
    d = RayDispatcher(ray_module=_FakeRayModule())
    assert d.name == "RayDispatcher"


async def test_ray_dispatcher_initializes_ray():
    fake = _FakeRayModule()
    d = RayDispatcher(ray_module=fake)
    knot = _build_knot()
    await d.dispatch(knot, {})
    assert len(fake.init_calls) == 1


async def test_ray_dispatcher_returns_result():
    fake = _FakeRayModule()
    d = RayDispatcher(ray_module=fake)
    knot = _build_knot()
    result = await d.dispatch(knot, {})
    assert isinstance(result, Ok)
    assert result.value == 84


async def test_ray_dispatcher_address_passed_to_init():
    fake = _FakeRayModule()
    d = RayDispatcher(address="ray://cluster:10001", ray_module=fake)
    knot = _build_knot()
    await d.dispatch(knot, {})
    assert fake.init_calls[0].get("address") == "ray://cluster:10001"


async def test_ray_dispatcher_shutdown():
    fake = _FakeRayModule()
    d = RayDispatcher(ray_module=fake)
    knot = _build_knot()
    await d.dispatch(knot, {})
    d.shutdown()
    assert fake.shutdown_calls == 1


# ---------------------------------------------------- Celery tests


async def test_celery_dispatcher_name():
    d = CeleryDispatcher(app=_FakeCeleryApp())
    assert d.name == "CeleryDispatcher"


async def test_celery_dispatcher_requires_app_or_broker():
    with pytest.raises(TypeError):
        CeleryDispatcher()


async def test_celery_dispatcher_uses_correct_task_name():
    app = _FakeCeleryApp()
    d = CeleryDispatcher(app=app)
    knot = _build_knot()
    # Register the task handler on the fake app so we get a real result
    # back.  We use the standard registration helper from production.
    from pirn.engine.dispatchers.celery_dispatcher import register_celery_worker_task

    register_celery_worker_task(app)
    result = await d.dispatch(knot, {})

    assert len(app.tasks_sent) == 1
    name, _ = app.tasks_sent[0]
    assert name == PIRN_CELERY_TASK_NAME
    assert isinstance(result, Ok)
    assert result.value == 84


async def test_celery_worker_task_runs_knot():
    """The register_celery_worker_task helper registers a task that,
    when called with (knot, inputs), runs the knot and returns its
    Result."""
    import concurrent.futures

    app = _FakeCeleryApp()
    from pirn.engine.dispatchers.celery_dispatcher import register_celery_worker_task

    register_celery_worker_task(app)
    handler = app.task_handlers[PIRN_CELERY_TASK_NAME]
    knot = _build_knot()
    # Real Celery workers have no event loop; mimic by running in a
    # thread so the handler's asyncio.run call has no enclosing loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(handler, knot, {}).result()
    assert isinstance(result, Ok)
    assert result.value == 84
