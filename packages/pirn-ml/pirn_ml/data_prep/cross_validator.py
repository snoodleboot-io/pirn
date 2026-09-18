"""``CrossValidator`` — partition a dataset into K shuffled, row-indexed folds.

Algorithm:
    1. Receive ``dataset`` (DatasetManifest or DatasetPayload), ``k`` (int >= 2),
       and ``random_seed`` (int) via process().
    2. Validate k >= 2 and dataset.row_count >= k.
    3. Shuffle the row positions ``0..n-1`` with a ``random.Random(random_seed)``
       permutation (Fisher-Yates), so the same seed always yields the same folds.
    4. Cut the permutation into k consecutive chunks: the first ``remainder``
       folds get one extra row.
    5. Hand the per-fold test rows to :class:`FoldPartitioner`, which emits one
       SplitManifest per fold with exact train/test ``row_indices``.

Math:
    base = n // k
    remainder = n - base * k
    test_count[i] = base + (1 if i < remainder else 0)
    train_count[i] = n - test_count[i]

References:
    - Kohavi, R. (1995). A study of cross-validation and bootstrap for accuracy
      estimation and model selection. *IJCAI*, 14(2), 1137-1145.
"""

from __future__ import annotations

import random
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.data_prep.fold_partitioner import FoldPartitioner
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.dataset_payload import DatasetPayload
from pirn_ml.types.split_manifest import SplitManifest


class CrossValidator(Knot):
    """Emit ``k`` shuffled, row-indexed folds of a dataset."""

    def __init__(
        self,
        *,
        dataset: Knot,
        k: Knot | int = 5,
        random_seed: Knot | int = 42,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dataset=dataset,
            k=k,
            random_seed=random_seed,
            _config=_config,
            **kwargs,
        )

    async def process(
        self, dataset: DatasetManifest | DatasetPayload, k: int = 5, random_seed: int = 42, **_: Any
    ) -> tuple[SplitManifest, ...]:
        """Shuffle the rows with ``random_seed`` and partition them into k balanced folds.

        Args:
            dataset: DatasetManifest (or DatasetPayload) whose row_count is partitioned.
            k: Number of folds; must be an int >= 2.
            random_seed: Seed for the row permutation; equal seeds give equal folds.

        Returns:
            Tuple of k SplitManifest objects whose train and test partitions carry
            their exact ``row_indices``; every row is in exactly one test partition.

        Raises:
            TypeError: If k or random_seed are not ints.
            ValueError: If k < 2 or dataset.row_count < k.
        """
        if isinstance(dataset, DatasetPayload):
            dataset = dataset.metadata
        if not isinstance(k, int):
            raise TypeError("CrossValidator: k must be an int")
        if k < 2:
            raise ValueError("CrossValidator: k must be >= 2")
        if not isinstance(random_seed, int):
            raise TypeError("CrossValidator: random_seed must be an int")
        total = int(dataset.row_count)
        if total < k:
            raise ValueError("CrossValidator: dataset.row_count must be at least k")
        order = list(range(total))
        random.Random(random_seed).shuffle(order)
        base = total // k
        remainder = total - base * k
        test_rows_per_fold: list[list[int]] = []
        start = 0
        for fold_index in range(k):
            test_count = base + (1 if fold_index < remainder else 0)
            test_rows_per_fold.append(order[start : start + test_count])
            start += test_count
        return FoldPartitioner.folds(dataset, test_rows_per_fold)
