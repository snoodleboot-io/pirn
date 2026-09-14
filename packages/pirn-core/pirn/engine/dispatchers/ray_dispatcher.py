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
from types import ModuleType
from typing import Any

from pirn.core.knot import Knot
from pirn.core.optional_dependency import OptionalDependency
from pirn.core.result import Result


class RayDispatcher:
    """Run knots on a Ray cluster (or local Ray instance)."""

    def __init__(
        self,
        *,
        address: str | None = None,
        ray_module: ModuleType | None = None,
    ) -> None:
        self._address = address
        # ``ray_module`` is injected by tests; production passes None and
        # we import ray lazily.
        self._ray: ModuleType | None = ray_module
        self._initialized = False

    @property
    def name(self) -> str:
        return "RayDispatcher"

    def _ensure_ray(self) -> ModuleType:
        if self._ray is not None:
            return self._ray
        ray = OptionalDependency.require("ray", extra="ray")
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

    async def dispatch(self, knot: Knot, inputs: Mapping[str, Any]) -> Result[Any]:
        self._ensure_init()
        ray = self._ensure_ray()

        # Build a remote function on demand.  In production we would
        # cache this per dispatcher instance, but the `@ray.remote`
        # decorator's result is also cached internally so the cost is
        # low.
        remote_fn = ray.remote(RayDispatcher._run_knot)
        ref = remote_fn.remote(knot, dict(inputs))

        # Bridge ray.get (blocking) to async via asyncio.to_thread.  The remote
        # function is ``_run_knot``, whose return value is the knot's ``Result``.
        outcome: Result[Any] = await asyncio.to_thread(ray.get, ref)
        return outcome

    @staticmethod
    def _run_knot(knot: Knot, inputs: dict[str, Any]) -> Result[Any]:
        """Run a knot in a Ray worker.

        A static method so the function Ray pickles by reference resolves
        through a normal import of this module, exactly like
        ``CeleryDispatcher._run_knot_sync``.
        """
        return asyncio.run(knot(inputs))

    def shutdown(self) -> None:
        if self._initialized and self._ray is not None:
            self._ray.shutdown()
            self._initialized = False
