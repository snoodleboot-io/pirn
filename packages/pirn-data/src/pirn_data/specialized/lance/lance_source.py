"""``LanceSource`` — Tier-4 source knot that opens a Lance dataset on disk.

Calls :func:`lance.dataset` against the configured path at run time and
emits a :class:`LanceDataset` adapter. The actual ``lance`` package
import happens inside :meth:`process` so this module imports cleanly
when ``lance`` is not installed.

Algorithm:
    1. Receive the resolved ``path`` string in ``process()``.
    2. Validate that ``path`` is a non-empty string.
    3. Import ``lance`` lazily (raises ``ImportError`` with install
       instructions if not available).
    4. Open the dataset via ``lance.dataset.LanceDataset(path)``.
    5. Wrap the result in a :class:`LanceDataset` and return it.

References:
    [1] Lance Python API — ``lance.dataset``:
        https://lancedb.github.io/lance/api/python/lance.html#lance.dataset
    [2] LanceDB / Lance file format overview:
        https://lancedb.github.io/lance/format.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source

from pirn_data.specialized.lance.lance_dataset import LanceDataset


class LanceSource(Source):
    """Open a Lance dataset at ``path`` and emit a :class:`LanceDataset`."""

    def __init__(
        self,
        *,
        path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(path=path, _config=_config, **kwargs)

    async def process(
        self,
        *,
        path: str,
        **_: Any,
    ) -> LanceDataset:
        """Open the configured Lance dataset path and return a LanceDataset adapter.

        Returns:
            A LanceDataset wrapping the opened Lance dataset.
        """
        if not isinstance(path, str) or not path:
            raise ValueError("LanceSource: path must be a non-empty string")

        from lance.dataset import LanceDataset as _LanceDataset

        dataset = _LanceDataset(path)
        return LanceDataset(dataset=dataset, source_uri=path)
