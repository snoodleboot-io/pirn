"""``BAMSortIndexer`` — sort and index a BAM file by coordinate or read name."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BAMSortIndexer(Knot):
    """Sort and index a BAM file by coordinate or read name."""

    _VALID_SORT_BY: frozenset[str] = frozenset({"coordinate", "name"})

    def __init__(
        self,
        *,
        bam_path: Knot,
        sort_by: str,
        threads: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(sort_by, str) or sort_by not in self._VALID_SORT_BY:
            raise ValueError(
                f"BAMSortIndexer: sort_by must be one of {sorted(self._VALID_SORT_BY)}"
            )
        if not isinstance(threads, int) or threads <= 0:
            raise ValueError("BAMSortIndexer: threads must be > 0")
        self._sort_by = sort_by
        self._threads = threads
        super().__init__(bam_path=bam_path, _config=_config, **kwargs)

    async def process(self, bam_path: str, **_: Any) -> dict[str, Any]:
        """Sort and index the BAM file and return paths to sorted BAM and index.

        Args:
            bam_path: File path to the input BAM file.

        Returns:
            Dict with ``sorted_bam_path``, ``index_path`` (None for name sort),
            and ``sort_by``.
        """
        if not isinstance(bam_path, str) or not bam_path:
            raise TypeError("BAMSortIndexer: bam_path must be a non-empty string")
        suffix = ".sorted.bam"
        sorted_path = bam_path.removesuffix(".bam") + suffix
        index_path = (sorted_path + ".bai") if self._sort_by == "coordinate" else None
        return {
            "sorted_bam_path": sorted_path,
            "index_path": index_path,
            "sort_by": self._sort_by,
        }
