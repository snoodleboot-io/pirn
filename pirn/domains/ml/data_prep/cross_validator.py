"""``CrossValidator`` — produce K logical :class:`DataSplit` folds.

Algorithm:
    1. Receive ``dataset`` (MLDataset), ``k`` (int >= 2), and ``random_seed`` via process().
    2. Validate k >= 2 and dataset.row_count >= k.
    3. Compute base fold size: ``base = row_count // k``.
    4. Distribute remainder rows: first ``remainder`` folds get one extra row.
    5. For each fold index, compute train count = total - test count.
    6. Construct a DataSplit with train/test MLDataset references per fold.
    7. Return a tuple of k DataSplit objects.

Math:
    base = total // k
    remainder = total - base * k
    test_count[i] = base + (1 if i < remainder else 0)
    train_count[i] = total - test_count[i]

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class CrossValidator(Knot):
    """Emit ``k`` logical folds of an :class:`MLDataset`."""

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
        self, dataset: MLDataset, k: int = 5, random_seed: int = 42, **_: Any
    ) -> tuple[DataSplit, ...]:
        """Partition the dataset into k balanced DataSplit folds and return the tuple of folds.

        Args:
            dataset: MLDataset reference whose row_count drives fold sizing.
            k: Number of folds; must be an int >= 2.
            random_seed: Random seed (reserved for future shuffle logic).

        Returns:
            Tuple of k DataSplit objects, each with a train and test MLDataset partition.

        Raises:
            TypeError: If k or random_seed are not ints.
            ValueError: If k < 2 or dataset.row_count < k.
        """
        if not isinstance(k, int):
            raise TypeError("CrossValidator: k must be an int")
        if k < 2:
            raise ValueError("CrossValidator: k must be >= 2")
        if not isinstance(random_seed, int):
            raise TypeError("CrossValidator: random_seed must be an int")
        total = int(dataset.row_count)
        if total < k:
            raise ValueError(
                "CrossValidator: dataset.row_count must be at least k"
            )
        base = total // k
        remainder = total - base * k
        now = datetime.now(timezone.utc)
        folds: list[DataSplit] = []
        for fold_index in range(k):
            test_count = base + (1 if fold_index < remainder else 0)
            train_count = total - test_count
            train = self._mk(dataset, fold_index, "train", train_count, now)
            test = self._mk(dataset, fold_index, "test", test_count, now)
            folds.append(DataSplit(train=train, test=test, validation=None))
        return tuple(folds)

    def _mk(
        self,
        source: MLDataset,
        fold_index: int,
        partition: str,
        count: int,
        fetched_at: datetime,
    ) -> MLDataset:
        return MLDataset(
            name=f"{source.name}:fold{fold_index}:{partition}",
            feature_names=source.feature_names,
            target_name=source.target_name,
            row_count=count,
            source_uri=source.source_uri,
            fetched_at=fetched_at,
        )
