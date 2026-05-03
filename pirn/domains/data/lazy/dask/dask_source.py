"""``DaskSource`` — pirn :class:`Source` that emits a deferred
:class:`DaskDataFrame`.

Two construction modes:

1. ``factory: Callable[[], dd.DataFrame]`` — caller supplies any zero-arg
   callable returning a ``dask.dataframe.DataFrame``. The most flexible
   form: works for ``dd.from_pandas(...)``, ``dd.from_delayed(...)``,
   custom registries, etc.
2. ``path`` + ``reader`` — the source calls
   ``reader(path, **reader_kwargs)``. For example,
   ``reader=dd.read_parquet`` or ``reader=dd.read_csv``.

Either ``factory`` or ``path`` must be supplied; not both.
"""

from __future__ import annotations

from typing import Any, Callable

import dask.dataframe as dd

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn.nodes.source import Source


class DaskSource(Source):
    """Bind a Dask data factory or path-based reader to emit a deferred frame."""

    def __init__(
        self,
        *,
        _config: KnotConfig,
        factory: Callable[[], dd.DataFrame] | None = None,
        path: str | None = None,
        reader: Callable[..., dd.DataFrame] | None = None,
        reader_kwargs: dict[str, Any] | None = None,
        backend_name: str = "dask",
        source_uri: str = "",
        **kwargs: Any,
    ) -> None:
        if factory is None and path is None:
            raise TypeError(
                "DaskSource: either factory or path must be supplied"
            )
        if factory is not None and path is not None:
            raise TypeError(
                "DaskSource: factory and path are mutually exclusive"
            )
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
        self._factory = factory
        self._path = path
        self._reader = reader
        self._reader_kwargs: dict[str, Any] = dict(reader_kwargs or {})
        self._backend_name = backend_name
        self._source_uri = source_uri or (path or "")
        super().__init__(_config=_config, **kwargs)

    @property
    def path(self) -> str | None:
        return self._path

    @property
    def backend_name(self) -> str:
        return self._backend_name

    async def process(self, **_: Any) -> DaskDataFrame:
        """Invoke the factory or path reader to build a deferred DaskDataFrame.

        Returns:
            A DaskDataFrame wrapping the newly created deferred Dask graph.
        """
        if self._factory is not None:
            frame = self._factory()
        else:
            assert self._reader is not None and self._path is not None
            frame = self._reader(self._path, **self._reader_kwargs)
        return DaskDataFrame(
            frame=frame,
            backend_name=self._backend_name,
            source_uri=self._source_uri,
        )
