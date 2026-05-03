"""``LanceSource`` — Tier-4 source knot that opens a Lance dataset on disk.

Calls :func:`lance.dataset` against the configured path at run time and
emits a :class:`LanceDataset` adapter. The actual ``lance`` package
import happens inside :meth:`process` so this module imports cleanly
when ``pylance`` is not installed.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.specialized.lance.lance_dataset import LanceDataset
from pirn.nodes.source import Source


class LanceSource(Source):
    """Open a Lance dataset at ``path`` and emit a :class:`LanceDataset`."""

    def __init__(
        self,
        *,
        path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(path, str) or not path:
            raise ValueError("LanceSource: path must be a non-empty string")
        self._path = path
        super().__init__(_config=_config, **kwargs)

    @property
    def path(self) -> str:
        return self._path

    async def process(self, **_: Any) -> LanceDataset:
        """Open the configured Lance dataset path and return a LanceDataset adapter.

        Returns:
            A LanceDataset wrapping the opened Lance dataset.
        """
        import lance

        dataset = lance.dataset(self._path)
        return LanceDataset(dataset=dataset, source_uri=self._path)
