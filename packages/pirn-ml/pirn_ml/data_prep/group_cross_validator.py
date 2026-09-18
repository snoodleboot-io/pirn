"""``GroupCrossValidator`` — K folds that never split a group across train and test.

All rows sharing a ``group_column`` value (a patient, a user, a well) land in
the same fold's test partition, so no group is ever seen by both the model
and its evaluation — the leakage plain k-fold allows for correlated rows.

Algorithm:
    1. Receive ``dataset`` (DatasetPayload), ``group_column``, and ``k`` via process().
    2. Validate k >= 2 and resolve the per-row group ids: the target vector when
       ``group_column`` is the manifest's ``target_name``, otherwise that
       feature column of the feature matrix.
    3. Reject fewer than k distinct groups — some fold would have an empty test set.
    4. Order groups by size, largest first (ties by first appearance), and assign
       each to the fold with the fewest rows so far (lowest fold index on ties).
    5. Hand the per-fold test rows to :class:`FoldPartitioner`.

Math:
    fold(g) = argmin_i |test_i|  for groups g in descending size order
    groups(test_i) and groups(train_i) are disjoint for every fold i

References:
    - Scikit-learn developers. ``sklearn.model_selection.GroupKFold`` — the same
      greedy largest-group-to-smallest-fold assignment.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.data_prep.fold_partitioner import FoldPartitioner
from pirn_ml.types.dataset_payload import DatasetPayload
from pirn_ml.types.split_manifest import SplitManifest


class GroupCrossValidator(Knot):
    """Emit ``k`` row-indexed folds with every group wholly inside one test partition."""

    def __init__(
        self,
        *,
        dataset: Knot,
        group_column: Knot | str,
        k: Knot | int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dataset=dataset,
            group_column=group_column,
            k=k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dataset: DatasetPayload,
        group_column: str = "",
        k: int = 5,
        **_: Any,
    ) -> tuple[SplitManifest, ...]:
        """Partition the rows into k folds with groups kept whole.

        Args:
            dataset: DatasetPayload whose group ids drive the partition.
            group_column: The target name or a feature name holding group ids.
            k: Number of folds; must be an int >= 2.

        Returns:
            Tuple of k SplitManifest objects with exact train/test ``row_indices``.

        Raises:
            TypeError: If dataset is not a DatasetPayload or k is not an int.
            ValueError: If k < 2, the column cannot be resolved, or there are fewer
                than k distinct groups.
        """
        if not isinstance(dataset, DatasetPayload):
            raise TypeError("GroupCrossValidator: dataset must be a DatasetPayload")
        if not isinstance(group_column, str) or not group_column:
            raise ValueError("GroupCrossValidator: group_column must be a non-empty string")
        if not isinstance(k, int):
            raise TypeError("GroupCrossValidator: k must be an int")
        if k < 2:
            raise ValueError("GroupCrossValidator: k must be >= 2")
        groups = FoldPartitioner.column_values(dataset, group_column, "GroupCrossValidator")
        rows_by_group: dict[object, list[int]] = {}
        for row, group in enumerate(groups):
            rows_by_group.setdefault(group, []).append(row)
        if len(rows_by_group) < k:
            raise ValueError(
                f"GroupCrossValidator: need at least k={k} distinct groups in "
                f"'{group_column}', got {len(rows_by_group)}"
            )
        # sorted() is stable, so equal-size groups keep first-appearance order.
        ordered = sorted(rows_by_group.values(), key=len, reverse=True)
        test_rows_per_fold: list[list[int]] = [[] for _ in range(k)]
        for group_rows in ordered:
            fold_sizes = [len(fold_rows) for fold_rows in test_rows_per_fold]
            smallest = fold_sizes.index(min(fold_sizes))
            test_rows_per_fold[smallest].extend(group_rows)
        return FoldPartitioner.folds(dataset.metadata, test_rows_per_fold)
