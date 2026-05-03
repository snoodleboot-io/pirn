"""``CrossValidator`` — produce K logical :class:`DataSplit` folds."""

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
        k: int = 5,
        random_seed: int = 42,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(k, int):
            raise TypeError("CrossValidator: k must be an int")
        if k < 2:
            raise ValueError("CrossValidator: k must be >= 2")
        if not isinstance(random_seed, int):
            raise TypeError("CrossValidator: random_seed must be an int")
        self._k = k
        self._random_seed = random_seed
        super().__init__(dataset=dataset, _config=_config, **kwargs)

    @property
    def k(self) -> int:
        return self._k

    async def process(
        self, dataset: MLDataset, **_: Any
    ) -> tuple[DataSplit, ...]:
        """Partition the dataset into k balanced DataSplit folds and return the tuple of folds.

        Args:
            dataset: MLDataset reference whose row_count drives fold sizing.

        Returns:
            Tuple of k DataSplit objects, each with a train and test MLDataset partition.

        Raises:
            ValueError: If dataset.row_count is less than k.
        """
        total = int(dataset.row_count)
        if total < self._k:
            raise ValueError(
                "CrossValidator: dataset.row_count must be at least k"
            )
        base = total // self._k
        remainder = total - base * self._k
        now = datetime.now(timezone.utc)
        folds: list[DataSplit] = []
        for fold_index in range(self._k):
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
