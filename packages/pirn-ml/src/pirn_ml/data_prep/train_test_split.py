"""``TrainTestSplit`` — partition an :class:`DatasetManifest` into train / val / test
references.

Pirn does not load the dataset rows here. Instead, it computes the
expected size of each partition deterministically from the
``random_seed`` and the upstream ``row_count`` and emits three
:class:`DatasetManifest` references (with adjusted ``row_count``) wrapped in a
:class:`SplitManifest`. Downstream knots that need actual rows resolve them
by streaming the source and filtering by hash-of-row-index against the
same seed.

Algorithm:
    1. Receive ``dataset``, ``test_fraction``, ``validation_fraction``, and
       ``random_seed`` via process().
    2. Validate fraction ranges and that their sum is < 1.
    3. Compute a small seed_bias from SHA-256(random_seed) to make splits seed-dependent.
    4. Compute test_count and optional validation_count from total * fractions + bias.
    5. Compute train_count = total - test_count - validation_count.
    6. Construct DatasetManifest references for each partition and wrap in a SplitManifest.

Math:
    seed_bias = (sha256_bytes[0:4] as uint32) / 2**32 - 0.5   # in (-0.5, 0.5)
    test_count = max(1, int(total * test_fraction + seed_bias))
    validation_count = max(1, int(total * validation_fraction + seed_bias))  [if > 0]
    train_count = total - test_count - validation_count

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.dataset_payload import DatasetPayload
from pirn_ml.types.split_manifest import SplitManifest


class TrainTestSplit(Knot):
    """Compute logical train/validation/test :class:`SplitManifest` from a dataset."""

    def __init__(
        self,
        *,
        dataset: Knot,
        test_fraction: Knot | float = 0.2,
        validation_fraction: Knot | float = 0.0,
        random_seed: Knot | int = 42,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dataset=dataset,
            test_fraction=test_fraction,
            validation_fraction=validation_fraction,
            random_seed=random_seed,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dataset: DatasetManifest | DatasetPayload,
        test_fraction: float = 0.2,
        validation_fraction: float = 0.0,
        random_seed: int = 42,
        **_: Any,
    ) -> SplitManifest:
        """Partition the dataset reference into train, test, and optional validation splits and return a SplitManifest.

        Args:
            dataset: DatasetManifest reference to partition.
            test_fraction: Fraction of rows for the test partition; must be in (0, 1).
            validation_fraction: Fraction of rows for the validation partition; must be in [0, 1).
            random_seed: Seed that introduces a small deterministic bias to split borders.

        Returns:
            SplitManifest with train, test, and optional validation DatasetManifest references.

        Raises:
            TypeError: If fraction or seed args have wrong types.
            ValueError: If dataset.row_count is negative or fractions exceed dataset size.
        """
        if isinstance(dataset, DatasetPayload):
            dataset = dataset.manifest
        if not isinstance(test_fraction, (int, float)):
            raise TypeError("TrainTestSplit: test_fraction must be numeric")
        if not isinstance(validation_fraction, (int, float)):
            raise TypeError("TrainTestSplit: validation_fraction must be numeric")
        if test_fraction <= 0.0 or test_fraction >= 1.0:
            raise ValueError("TrainTestSplit: test_fraction must be in (0, 1)")
        if validation_fraction < 0.0 or validation_fraction >= 1.0:
            raise ValueError("TrainTestSplit: validation_fraction must be in [0, 1)")
        if test_fraction + validation_fraction >= 1.0:
            raise ValueError("TrainTestSplit: test_fraction + validation_fraction must be < 1")
        if not isinstance(random_seed, int):
            raise TypeError("TrainTestSplit: random_seed must be an int")
        total = int(dataset.row_count)
        if total < 0:
            raise ValueError("TrainTestSplit: dataset.row_count must be non-negative")
        # Deterministic offsets — seed influences the split borders very
        # slightly so two seeds produce repeatable but different splits.
        seed_bias = self._seed_bias(random_seed)
        test_count = max(1, int(total * float(test_fraction) + seed_bias))
        validation_count = (
            max(1, int(total * float(validation_fraction) + seed_bias))
            if validation_fraction > 0.0
            else 0
        )
        if test_count + validation_count >= total:
            raise ValueError("TrainTestSplit: requested fractions exceed dataset size")
        train_count = total - test_count - validation_count
        now = datetime.now(UTC)
        train = self._mk(dataset, "train", train_count, now)
        test = self._mk(dataset, "test", test_count, now)
        validation = (
            self._mk(dataset, "validation", validation_count, now) if validation_count > 0 else None
        )
        return SplitManifest(train=train, test=test, validation=validation)

    def _seed_bias(self, random_seed: int) -> float:
        # Map the seed into [0, 1) so the bias is small but seed-dependent.
        digest = hashlib.sha256(str(random_seed).encode("utf-8")).digest()
        # Use the first 4 bytes for a stable float bias.
        scaled = int.from_bytes(digest[:4], "big") / float(0x100000000)
        return scaled - 0.5  # centred at 0; magnitude < 0.5

    def _mk(
        self,
        source: DatasetManifest,
        partition: str,
        count: int,
        fetched_at: datetime,
    ) -> DatasetManifest:
        return DatasetManifest(
            name=f"{source.name}:{partition}",
            feature_names=source.feature_names,
            target_name=source.target_name,
            row_count=count,
            source_uri=source.source_uri,
            fetched_at=fetched_at,
        )
