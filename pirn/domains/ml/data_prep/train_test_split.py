"""``TrainTestSplit`` — partition an :class:`MLDataset` into train / val / test
references.

Pirn does not load the dataset rows here. Instead, it computes the
expected size of each partition deterministically from the
``random_seed`` and the upstream ``row_count`` and emits three
:class:`MLDataset` references (with adjusted ``row_count``) wrapped in a
:class:`DataSplit`. Downstream knots that need actual rows resolve them
by streaming the source and filtering by hash-of-row-index against the
same seed.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class TrainTestSplit(Knot):
    """Compute logical train/validation/test :class:`DataSplit` from a dataset."""

    def __init__(
        self,
        *,
        dataset: Knot,
        test_fraction: float = 0.2,
        validation_fraction: float = 0.0,
        random_seed: int = 42,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(test_fraction, (int, float)):
            raise TypeError("TrainTestSplit: test_fraction must be numeric")
        if not isinstance(validation_fraction, (int, float)):
            raise TypeError(
                "TrainTestSplit: validation_fraction must be numeric"
            )
        if test_fraction <= 0.0 or test_fraction >= 1.0:
            raise ValueError(
                "TrainTestSplit: test_fraction must be in (0, 1)"
            )
        if validation_fraction < 0.0 or validation_fraction >= 1.0:
            raise ValueError(
                "TrainTestSplit: validation_fraction must be in [0, 1)"
            )
        if test_fraction + validation_fraction >= 1.0:
            raise ValueError(
                "TrainTestSplit: test_fraction + validation_fraction must be < 1"
            )
        if not isinstance(random_seed, int):
            raise TypeError("TrainTestSplit: random_seed must be an int")
        self._test_fraction = float(test_fraction)
        self._validation_fraction = float(validation_fraction)
        self._random_seed = random_seed
        super().__init__(dataset=dataset, _config=_config, **kwargs)

    @property
    def random_seed(self) -> int:
        return self._random_seed

    async def process(
        self, dataset: MLDataset, **_: Any
    ) -> DataSplit:
        total = int(dataset.row_count)
        if total < 0:
            raise ValueError(
                "TrainTestSplit: dataset.row_count must be non-negative"
            )
        # Deterministic offsets — seed influences the split borders very
        # slightly so two seeds produce repeatable but different splits.
        seed_bias = self._seed_bias()
        test_count = max(1, int(total * self._test_fraction + seed_bias))
        validation_count = (
            max(1, int(total * self._validation_fraction + seed_bias))
            if self._validation_fraction > 0.0
            else 0
        )
        if test_count + validation_count >= total:
            raise ValueError(
                "TrainTestSplit: requested fractions exceed dataset size"
            )
        train_count = total - test_count - validation_count
        now = datetime.now(timezone.utc)
        train = self._mk(dataset, "train", train_count, now)
        test = self._mk(dataset, "test", test_count, now)
        validation = (
            self._mk(dataset, "validation", validation_count, now)
            if validation_count > 0
            else None
        )
        return DataSplit(train=train, test=test, validation=validation)

    def _seed_bias(self) -> float:
        # Map the seed into [0, 1) so the bias is small but seed-dependent.
        digest = hashlib.sha256(
            str(self._random_seed).encode("utf-8")
        ).digest()
        # Use the first 4 bytes for a stable float bias.
        scaled = int.from_bytes(digest[:4], "big") / float(0x100000000)
        return scaled - 0.5  # centred at 0; magnitude < 0.5

    def _mk(
        self,
        source: MLDataset,
        partition: str,
        count: int,
        fetched_at: datetime,
    ) -> MLDataset:
        return MLDataset(
            name=f"{source.name}:{partition}",
            feature_names=source.feature_names,
            target_name=source.target_name,
            row_count=count,
            source_uri=source.source_uri,
            fetched_at=fetched_at,
        )
