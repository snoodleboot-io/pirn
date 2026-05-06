"""``BAMSortIndexer`` — sort and index a BAM file by coordinate or read name.

Algorithm:
    1. Receive a bam_path string, sort_by string, and threads int.
    2. Validate types and that sort_by is one of coordinate/name and threads > 0.
    3. Sort the BAM using samtools sort with the specified ordering and thread count.
    4. Index the sorted BAM (coordinate sort only).
    5. Return the sorted BAM path and index path.


References:
    - samtools sort: https://www.htslib.org/doc/samtools-sort.html
    - samtools index: https://www.htslib.org/doc/samtools-index.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BAMSortIndexer(Knot):
    """Sort and index a BAM file by coordinate or read name."""

    def __init__(
        self,
        *,
        bam_path: Knot | str,
        sort_by: Knot | str,
        threads: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            bam_path=bam_path,
            sort_by=sort_by,
            threads=threads,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        bam_path: str,
        sort_by: str,
        threads: int,
        **_: Any,
    ) -> dict[str, Any]:
        """Sort and index the BAM file and return paths to sorted BAM and index.

        Args:
            bam_path: Non-empty file path to the input BAM file.
            sort_by: Sort order; one of 'coordinate', 'name'.
            threads: Positive integer number of threads for sorting.

        Returns:
            Dict with ``sorted_bam_path``, ``index_path`` (None for name sort),
            and ``sort_by``.

        Raises:
            TypeError: If bam_path is not a non-empty string.
            ValueError: If sort_by is invalid or threads is non-positive.
        """
        if not isinstance(sort_by, str) or sort_by not in {"coordinate", "name"}:
            raise ValueError("BAMSortIndexer: sort_by must be one of ['coordinate', 'name']")
        if not isinstance(threads, int) or threads <= 0:
            raise ValueError("BAMSortIndexer: threads must be > 0")
        if not isinstance(bam_path, str) or not bam_path:
            raise TypeError("BAMSortIndexer: bam_path must be a non-empty string")
        suffix = ".sorted.bam"
        sorted_path = bam_path.removesuffix(".bam") + suffix
        index_path = (sorted_path + ".bai") if sort_by == "coordinate" else None
        return {
            "sorted_bam_path": sorted_path,
            "index_path": index_path,
            "sort_by": sort_by,
        }
