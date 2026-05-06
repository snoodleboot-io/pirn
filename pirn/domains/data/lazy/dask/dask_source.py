"""``DaskSource`` — pirn :class:`Source` that emits a deferred
:class:`DaskDataFrame`.

Two construction modes:

1. ``factory: Knot | Callable[[], dd.DataFrame]`` — caller supplies any zero-arg
   callable returning a ``dask.dataframe.DataFrame``. The most flexible
   form: works for ``dd.from_pandas(...)``, ``dd.from_delayed(...)``,
   custom registries, etc.
2. ``path`` + ``reader`` — the source calls
   ``reader(path, **reader_kwargs)``. For example,
   ``reader=dd.read_parquet`` or ``reader=dd.read_csv``.

Either ``factory`` or ``path`` must be supplied; not both.

Algorithm:
    1. Receive resolved ``factory``, ``path``, ``reader``, ``reader_kwargs``,
       ``backend_name``, and ``source_uri`` values in ``process()``.
    2. Validate mutual exclusion: exactly one of ``factory`` or ``path`` must
       be provided; ``path`` mode requires a callable ``reader``.
    3. If ``factory`` is supplied, call ``factory()`` to obtain the deferred
       ``dask.dataframe.DataFrame``.
    4. Otherwise call ``reader(path, **reader_kwargs)`` to obtain the frame.
    5. Wrap the frame in a :class:`DaskDataFrame` and return it.

References:
    [1] Dask DataFrame API — ``dask.dataframe``:
        https://docs.dask.org/en/stable/dataframe.html
    [2] Dask delayed readers (``read_parquet``, ``read_csv``, etc.):
        https://docs.dask.org/en/stable/dataframe-create.html
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import dask.dataframe as dd

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn.core.knot import Knot
from pirn.nodes.source import Source


class DaskSource(Source):
    """Bind a Dask data factory or path-based reader to emit a deferred frame."""

    def __init__(
        self,
        *,
        _config: KnotConfig,
        factory: Knot | Callable[[], dd.DataFrame] | None = None,
        path: Knot | str | None = None,
        reader: Knot | Callable[..., dd.DataFrame] | None = None,
        reader_kwargs: Knot | dict[str, Any] | None = None,
        backend_name: Knot | str = "dask",
        source_uri: Knot | str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            factory=factory,
            path=path,
            reader=reader,
            reader_kwargs=reader_kwargs,
            backend_name=backend_name,
            source_uri=source_uri,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        factory: Callable[[], dd.DataFrame] | None = None,
        path: str | None = None,
        reader: Callable[..., dd.DataFrame] | None = None,
        reader_kwargs: dict[str, Any] | None = None,
        backend_name: str = "dask",
        source_uri: str = "",
        **_: Any,
    ) -> DaskDataFrame:
        """Invoke the factory or path reader to build a deferred DaskDataFrame.

        Returns:
            A DaskDataFrame wrapping the newly created deferred Dask graph.
        """
        if factory is None and path is None:
            raise TypeError("DaskSource: either factory or path must be supplied")
        if factory is not None and path is not None:
            raise TypeError("DaskSource: factory and path are mutually exclusive")
        if factory is not None and not callable(factory):
            raise TypeError(
                "DaskSource: factory must be a callable () -> dask.dataframe.DataFrame"
            )
        if path is not None:
            if not isinstance(path, str) or not path:
                raise ValueError("DaskSource: path must be a non-empty string")
            if reader is None:
                raise TypeError(
                    "DaskSource: reader is required when path is supplied "
                    "(e.g. reader=dask.dataframe.read_parquet)"
                )
            if not callable(reader):
                raise TypeError("DaskSource: reader must be callable")

        resolved_kwargs: dict[str, Any] = dict(reader_kwargs or {})
        resolved_uri = source_uri or (path or "")

        if factory is not None:
            frame = factory()
        else:
            assert reader is not None and path is not None
            frame = reader(path, **resolved_kwargs)

        return DaskDataFrame(
            frame=frame,
            backend_name=backend_name,
            source_uri=resolved_uri,
        )
