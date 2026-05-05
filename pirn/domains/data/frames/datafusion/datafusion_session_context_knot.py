"""``DatafusionSessionContextKnot`` — vending Knot for :class:`DatafusionSessionContext`.

A :class:`datafusion.SessionContext` is a live Rust-backed object that cannot
travel through the pirn graph (not serialisable, holds a native extension
handle). This vending Knot constructs one during ``process()`` and returns it
wrapped in a pydantic-opaque :class:`DatafusionSessionContext` so that consumer
Knots can declare it as a typed upstream dependency and receive the resolved
wrapper in their own ``process()`` calls.

Share a single :class:`DatafusionSessionContextKnot` across all Knots that
need to operate on the same in-process DataFusion engine.

Algorithm:
    1. Instantiate :class:`datafusion.SessionContext` with default settings.
    2. Wrap in :class:`DatafusionSessionContext` for pydantic compatibility.
    3. Return the wrapper so downstream Knots receive it as a resolved value.

References:
    [1] Apache DataFusion Python — SessionContext:
        https://datafusion.apache.org/python/autoapi/datafusion/index.html#datafusion.SessionContext
"""

from __future__ import annotations

from typing import Any

import datafusion as df

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.datafusion.datafusion_session_context import (
    DatafusionSessionContext,
)


class DatafusionSessionContextKnot(Knot):
    """Construct and vend a :class:`DatafusionSessionContext`.

    No inputs beyond ``_config`` — the context is stateless at construction
    time. Downstream Knots declare this Knot as a typed ``__init__`` parameter
    and receive the :class:`DatafusionSessionContext` wrapper in ``process()``.
    """

    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DatafusionSessionContext:
        """Construct and return a wrapped DataFusion SessionContext.

        Returns:
            A :class:`DatafusionSessionContext` wrapping a fresh
            :class:`datafusion.SessionContext`.
        """
        return DatafusionSessionContext(ctx=df.SessionContext())
