"""``FoldPartitioner`` — shared row-level fold construction for the cross-validators.

:class:`~pirn_ml.data_prep.cross_validator.CrossValidator`,
:class:`~pirn_ml.data_prep.stratified_cross_validator.StratifiedCrossValidator`
and :class:`~pirn_ml.data_prep.group_cross_validator.GroupCrossValidator`
differ only in *which* rows land in each fold's test partition. Each decides
that assignment, then hands the per-fold test rows to :meth:`FoldPartitioner.folds`,
which turns them into ``k`` :class:`SplitManifest` values whose train and test
:class:`DatasetManifest` references carry their exact ``row_indices``.

Algorithm:
    1. Receive the source manifest and one list of test-row positions per fold.
    2. Check the lists partition ``range(row_count)`` exactly (every row in
       exactly one test fold).
       Positions are relative to the source; when the source is itself a
       partition they are mapped through its ``row_indices``.
    3. For fold ``i``: test rows = sorted fold list; train rows = every other
       row, in source order.
    4. Emit one SplitManifest per fold.

Math:
    test_i and test_j are disjoint (i != j); the union of all test_i is {0..n-1}
    train_i = {0..n-1} minus test_i

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.dataset_payload import DatasetPayload
from pirn_ml.types.split_manifest import SplitManifest


class FoldPartitioner:
    """Build row-indexed k-fold :class:`SplitManifest` values from per-fold test rows."""

    @staticmethod
    def folds(
        source: DatasetManifest, test_rows_per_fold: Sequence[Sequence[int]]
    ) -> tuple[SplitManifest, ...]:
        """Return one SplitManifest per fold for a partition of the source rows.

        Raises:
            ValueError: If the fold lists do not partition ``range(source.row_count)``.
        """
        total = int(source.row_count)
        assigned = sorted(row for fold in test_rows_per_fold for row in fold)
        if assigned != list(range(total)):
            raise ValueError(
                "FoldPartitioner: test folds must partition every source row exactly once"
            )
        now = datetime.now(UTC)
        folds: list[SplitManifest] = []
        for fold_index, fold_rows in enumerate(test_rows_per_fold):
            test_rows = tuple(sorted(fold_rows))
            in_test = set(test_rows)
            train_rows = tuple(row for row in range(total) if row not in in_test)
            folds.append(
                SplitManifest(
                    train=FoldPartitioner._partition(source, fold_index, "train", train_rows, now),
                    test=FoldPartitioner._partition(source, fold_index, "test", test_rows, now),
                    validation=None,
                )
            )
        return tuple(folds)

    @staticmethod
    def column_values(dataset: DatasetPayload, column: str, owner: str) -> list[object]:
        """Per-row values of ``column`` — the target vector or one feature column.

        Raises:
            ValueError: If ``column`` is neither the target nor a feature, the
                target vector is absent, or the arrays disagree with ``row_count``.
        """
        manifest = dataset.metadata
        if column == manifest.target_name:
            target = dataset.data.target_vector
            if target is None:
                raise ValueError(f"{owner}: dataset has no target vector for '{column}'")
            values: list[object] = list(target.tolist())
        elif column in manifest.feature_names:
            column_index = manifest.feature_names.index(column)
            values = list(dataset.data.feature_matrix[:, column_index].tolist())
        else:
            raise ValueError(
                f"{owner}: column '{column}' is neither the target "
                f"({manifest.target_name!r}) nor a feature {list(manifest.feature_names)}"
            )
        if len(values) != int(manifest.row_count):
            raise ValueError(
                f"{owner}: '{column}' has {len(values)} values but the manifest "
                f"declares row_count={manifest.row_count}"
            )
        return values

    @staticmethod
    def _partition(
        source: DatasetManifest,
        fold_index: int,
        partition: str,
        rows: tuple[int, ...],
        fetched_at: datetime,
    ) -> DatasetManifest:
        # Positions are relative to the source; a source that is itself a
        # partition maps them back onto its own row_indices.
        source_rows = tuple(source.row_indices[row] for row in rows) if source.row_indices else rows
        return DatasetManifest(
            name=f"{source.name}:fold{fold_index}:{partition}",
            feature_names=source.feature_names,
            target_name=source.target_name,
            row_count=len(rows),
            source_uri=source.source_uri,
            fetched_at=fetched_at,
            row_indices=source_rows,
        )
