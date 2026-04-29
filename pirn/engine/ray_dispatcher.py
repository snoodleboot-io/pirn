"""Ray-backed dispatcher.

Submits each knot as a Ray remote task.  Workers run the knot in a
freshly-spun event loop (the same model as ThreadDispatcher and
DaskDispatcher).

Construction:

* ``RayDispatcher()`` — connects to or starts the local Ray instance
  on first use (``ray.init`` is called lazily).
* ``RayDispatcher(address="ray://...")`` — connect to a remote Ray
  cluster.

Caveats:

* Ray's serialization is more restrictive than Dask's.  Knots holding
  closures over local variables may not serialize.
* ``ray.get`` is blocking; we use ``asyncio.to_thread`` to await
  without blocking the dispatcher's event loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.result import Result


class RayDispatcher:
    """Run knots on a Ray cluster (or local Ray instance)."""

    def __init__(
        self,
        *,
        address: str | None = None,
        ray_module: Any = None,
    ) -> None:
        self._address = address
        # ``ray_module`` is injected by tests; production passes None and
        # we import ray lazily.
        self._ray = ray_module
        self._initialized = False

    @property
    def name(self) -> str:
        return "RayDispatcher"

    def _ensure_ray(self) -> Any:
        if self._ray is not None:
            return self._ray
        try:
            import ray
        except ImportError as exc:
            raise ImportError(
                "RayDispatcher requires ray; install via `pip install pirn[ray]`"
            ) from exc
        self._ray = ray
        return ray

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        ray = self._ensure_ray()
        if self._address is not None:
            ray.init(address=self._address, ignore_reinit_error=True)
        else:
            ray.init(ignore_reinit_error=True)
        self._initialized = True

    async def dispatch(
        self, knot: Knot, inputs: Mapping[str, Any]
    ) -> Result[Any]:
        self._ensure_init()
        ray = self._ensure_ray()

        # Build a remote function on demand.  In production we would
        # cache this per dispatcher instance, but the `@ray.remote`
        # decorator's result is also cached internally so the cost is
        # low.
        remote_fn = ray.remote(_ray_run_knot)
        ref = remote_fn.remote(knot, dict(inputs))

        # Bridge ray.get (blocking) to async via asyncio.to_thread.
        return await asyncio.to_thread(ray.get, ref)

    def shutdown(self) -> None:
        if self._initialized and self._ray is not None:
            self._ray.shutdown()
            self._initialized = False


def _ray_run_knot(knot: Knot, inputs: dict[str, Any]) -> Result[Any]:
    """Run a knot in a Ray worker."""
    return asyncio.run(knot(inputs))
