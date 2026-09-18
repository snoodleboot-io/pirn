"""``StratifiedCrossValidator`` — K folds that preserve class proportions.

Every fold's test partition holds (to within one row) the same share of each
class of ``stratify_column`` as the whole dataset, so a rare class is present
in every fold instead of landing in one of them by chance.

Algorithm:
    1. Receive ``dataset`` (DatasetPayload), ``stratify_column``, ``k``, and
       ``random_seed`` via process().
    2. Validate k >= 2 and resolve the per-row class labels: the target vector
       when ``stratify_column`` is the manifest's ``target_name``, otherwise
       that feature column of the feature matrix.
    3. Reject any class with fewer than k rows — it cannot appear in every
       fold's test partition.
    4. For each class (in first-seen order): shuffle its rows with the seeded
       generator and deal ``n_c // k`` rows to every fold; the ``n_c mod k``
       left-over rows go to the folds after a rotating offset, so the leftovers
       of successive classes spread over different folds and fold sizes stay
       within one row of each other.
    5. Hand the per-fold test rows to :class:`FoldPartitioner`.

Math:
    count(c, i) = floor(n_c / k) + [ (i - offset_c) mod k < n_c mod k ]
    offset_{c+1} = (offset_c + n_c mod k) mod k
    |count(c, i) / |test_i| - n_c / n| -> 0, and |count(c, i) - n_c / k| < 1

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
from pirn_ml.types.dataset_payload import DatasetPayload
from pirn_ml.types.split_manifest import SplitManifest


class StratifiedCrossValidator(Knot):
    """Emit ``k`` row-indexed folds whose test partitions preserve class proportions."""

    def __init__(
        self,
        *,
        dataset: Knot,
        stratify_column: Knot | str,
        k: Knot | int = 5,
        random_seed: Knot | int = 42,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dataset=dataset,
            stratify_column=stratify_column,
            k=k,
            random_seed=random_seed,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dataset: DatasetPayload,
        stratify_column: str = "",
        k: int = 5,
        random_seed: int = 42,
        **_: Any,
    ) -> tuple[SplitManifest, ...]:
        """Partition the rows into k folds stratified on ``stratify_column``.

        Args:
            dataset: DatasetPayload whose labels drive the stratification.
            stratify_column: The target name or a feature name holding class labels.
            k: Number of folds; must be an int >= 2.
            random_seed: Seed for the within-class row shuffle.

        Returns:
            Tuple of k SplitManifest objects with exact train/test ``row_indices``.

        Raises:
            TypeError: If dataset is not a DatasetPayload or k/random_seed are not ints.
            ValueError: If k < 2, the column cannot be resolved, or a class has fewer
                than k rows.
        """
        if not isinstance(dataset, DatasetPayload):
            raise TypeError("StratifiedCrossValidator: dataset must be a DatasetPayload")
        if not isinstance(stratify_column, str) or not stratify_column:
            raise ValueError("StratifiedCrossValidator: stratify_column must be a non-empty string")
        if not isinstance(k, int):
            raise TypeError("StratifiedCrossValidator: k must be an int")
        if k < 2:
            raise ValueError("StratifiedCrossValidator: k must be >= 2")
        if not isinstance(random_seed, int):
            raise TypeError("StratifiedCrossValidator: random_seed must be an int")
        labels = FoldPartitioner.column_values(dataset, stratify_column, "StratifiedCrossValidator")
        rows_by_class: dict[object, list[int]] = {}
        for row, label in enumerate(labels):
            rows_by_class.setdefault(label, []).append(row)
        too_small = {label: len(rows) for label, rows in rows_by_class.items() if len(rows) < k}
        if too_small:
            raise ValueError(
                f"StratifiedCrossValidator: every class needs at least k={k} rows; "
                f"too small: {too_small}"
            )
        generator = random.Random(random_seed)
        test_rows_per_fold: list[list[int]] = [[] for _ in range(k)]
        offset = 0
        for class_rows in rows_by_class.values():
            shuffled = list(class_rows)
            generator.shuffle(shuffled)
            per_fold, leftover = divmod(len(shuffled), k)
            counts = [per_fold] * k
            for step in range(leftover):
                counts[(offset + step) % k] += 1
            offset = (offset + leftover) % k
            start = 0
            for fold_index, count in enumerate(counts):
                test_rows_per_fold[fold_index].extend(shuffled[start : start + count])
                start += count
        return FoldPartitioner.folds(dataset.metadata, test_rows_per_fold)
