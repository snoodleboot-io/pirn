"""``IbisConnectionKnot`` — vending Knot for :class:`IbisConnection`.

An Ibis backend connection is a live, engine-backed object that cannot
travel through the pirn graph (not serialisable, holds a native extension
handle). This vending Knot constructs one during ``process()`` and returns
it wrapped in a pydantic-opaque :class:`IbisConnection` so that consumer
Knots can declare it as a typed upstream dependency and receive the resolved
wrapper in their own ``process()`` calls.

Share a single :class:`IbisConnectionKnot` across all Knots that need to
operate on the same Ibis backend.

Algorithm:
    1. Receive the caller-supplied Ibis backend connection object (any object
       satisfying the ``connection.table(name)`` contract).
    2. Wrap the backend in :class:`IbisConnection` for pydantic compatibility.
    3. Return the wrapper so downstream Knots receive it as a resolved value.

References:
    [1] Ibis Project — backends and connections:
        https://ibis-project.org/backends/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.lazy.ibis.ibis_connection import IbisConnection


class IbisConnectionKnot(Knot):
    """Construct and vend an :class:`IbisConnection`.

    Pass a live Ibis backend connection as ``backend``. Downstream Knots
    declare this Knot as a typed ``__init__`` parameter and receive the
    :class:`IbisConnection` wrapper in ``process()``.
    """

    def __init__(self, *, backend: Knot | Any, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(backend=backend, _config=_config, **kwargs)

    async def process(self, *, backend: Any, **_: Any) -> IbisConnection:
        """Wrap the supplied Ibis backend in an :class:`IbisConnection`.

        Args:
            backend: A live Ibis backend connection (any object whose
                ``table(name)`` method returns an Ibis table expression).

        Returns:
            An :class:`IbisConnection` wrapping the backend.
        """
        return IbisConnection(backend=backend)
