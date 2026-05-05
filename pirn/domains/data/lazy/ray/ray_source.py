"""``RaySource`` — pirn :class:`Source` that emits a deferred
:class:`RayDataset`.

Two construction modes:

1. ``factory: Callable[[], ray.data.Dataset]`` — caller supplies any
   zero-arg callable returning a ``ray.data.Dataset``. This is the
   most flexible form: works for ``ray.data.from_pandas(...)``,
   ``ray.data.from_items(...)``, ``ray.data.read_parquet(...)``, etc.
2. ``path`` + ``reader`` — the source calls
   ``reader(path, **reader_kwargs)``. For example,
   ``reader=ray.data.read_parquet``.

Important: pirn never calls ``ray.init()`` here. The caller is
responsible for managing the Ray runtime if their factory/reader
requires one.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import ray.data

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.nodes.source import Source


class RaySource(Source):
    """Bind a Ray Data factory or path-based reader to emit a deferred dataset."""

    def __init__(
        self,
        *,
        _config: KnotConfig,
        factory: Callable[[], ray.data.Dataset] | None = None,
        path: str | None = None,
        reader: Callable[..., ray.data.Dataset] | None = None,
        reader_kwargs: dict[str, Any] | None = None,
        backend_name: str = "ray",
        source_uri: str = "",
        **kwargs: Any,
    ) -> None:
        if factory is None and path is None:
            raise TypeError(
                "RaySource: either factory or path must be supplied"
            )
        if factory is not None and path is not None:
            raise TypeError(
                "RaySource: factory and path are mutually exclusive"
            )
        if factory is not None and not callable(factory):
            raise TypeError(
                "RaySource: factory must be a callable () -> ray.data.Dataset"
            )
        if path is not None:
            if not isinstance(path, str) or not path:
                raise ValueError("RaySource: path must be a non-empty string")
            if reader is None:
                raise TypeError(
                    "RaySource: reader is required when path is supplied "
                    "(e.g. reader=ray.data.read_parquet)"
                )
            if not callable(reader):
                raise TypeError("RaySource: reader must be callable")
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

    async def process(self, **_: Any) -> RayDataset:
        """Invoke the factory or path reader to build a deferred RayDataset.

        Returns:
            A RayDataset wrapping the newly created deferred Ray Data plan.
        """
        if self._factory is not None:
            dataset = self._factory()
        else:
            assert self._reader is not None and self._path is not None
            dataset = self._reader(self._path, **self._reader_kwargs)
        return RayDataset(
            dataset=dataset,
            backend_name=self._backend_name,
            source_uri=self._source_uri,
        )
