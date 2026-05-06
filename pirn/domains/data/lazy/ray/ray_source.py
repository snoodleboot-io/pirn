"""``RaySource`` — pirn :class:`Source` that emits a deferred
:class:`RayDataset`.

Two construction modes:

1. ``factory: Knot | Callable[[], ray.data.Dataset]`` — caller supplies any
   zero-arg callable returning a ``ray.data.Dataset``. This is the
   most flexible form: works for ``ray.data.from_pandas(...)``,
   ``ray.data.from_items(...)``, ``ray.data.read_parquet(...)``, etc.
2. ``path`` + ``reader`` — the source calls
   ``reader(path, **reader_kwargs)``. For example,
   ``reader=ray.data.read_parquet``.

Important: pirn never calls ``ray.init()`` here. The caller is
responsible for managing the Ray runtime if their factory/reader
requires one.

Algorithm:
    1. Receive resolved ``factory``, ``path``, ``reader``, ``reader_kwargs``,
       ``backend_name``, and ``source_uri`` values in ``process()``.
    2. Validate mutual exclusion: exactly one of ``factory`` or ``path`` must
       be provided; ``path`` mode requires a callable ``reader``.
    3. If ``factory`` is supplied, call ``factory()`` to obtain the deferred
       ``ray.data.Dataset``.
    4. Otherwise call ``reader(path, **reader_kwargs)`` to obtain the dataset.
    5. Wrap the dataset in a :class:`RayDataset` and return it.

References:
    [1] Ray Data — Dataset creation:
        https://docs.ray.io/en/latest/data/creating-datasets.html
    [2] Ray Data — Reading data from storage:
        https://docs.ray.io/en/latest/data/loading-data.html
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import ray.data

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.core.knot import Knot
from pirn.nodes.source import Source


class RaySource(Source):
    """Bind a Ray Data factory or path-based reader to emit a deferred dataset."""

    def __init__(
        self,
        *,
        _config: KnotConfig,
        factory: Knot | Callable[[], ray.data.Dataset] | None = None,
        path: Knot | str | None = None,
        reader: Knot | Callable[..., ray.data.Dataset] | None = None,
        reader_kwargs: Knot | dict[str, Any] | None = None,
        backend_name: Knot | str = "ray",
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
        factory: Callable[[], ray.data.Dataset] | None = None,
        path: str | None = None,
        reader: Callable[..., ray.data.Dataset] | None = None,
        reader_kwargs: dict[str, Any] | None = None,
        backend_name: str = "ray",
        source_uri: str = "",
        **_: Any,
    ) -> RayDataset:
        """Invoke the factory or path reader to build a deferred RayDataset.

        Returns:
            A RayDataset wrapping the newly created deferred Ray Data plan.
        """
        if factory is None and path is None:
            raise TypeError("RaySource: either factory or path must be supplied")
        if factory is not None and path is not None:
            raise TypeError("RaySource: factory and path are mutually exclusive")
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

        resolved_kwargs: dict[str, Any] = dict(reader_kwargs or {})
        resolved_uri = source_uri or (path or "")

        if factory is not None:
            dataset = factory()
        else:
            assert reader is not None and path is not None
            dataset = reader(path, **resolved_kwargs)

        return RayDataset(
            dataset=dataset,
            backend_name=backend_name,
            source_uri=resolved_uri,
        )
