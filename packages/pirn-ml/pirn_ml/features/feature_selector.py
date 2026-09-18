"""``FeatureSelector`` — keep the ``k`` best-scoring features of a train/test split.

Scores every feature on the **training** partition only (so the test partition
never informs the choice), keeps the ``k`` highest-ranked columns, and returns
the split with both partitions' arrays and feature schemas reduced to them.

Algorithm:
    1. Receive ``split`` (DataSplitPayload), ``k`` (int >= 1), and ``method`` via process().
    2. Validate ``k`` against the feature count, ``method`` against
       ``valid_methods``, and that the train/test arrays match the manifest's
       feature names.
    3. Score features on ``X_train`` with the selected method (``y_train`` is
       required for ``mutual_information`` and ``rfe``):

       * ``variance`` — per-column population variance.
       * ``mutual_information`` — estimated MI between each feature and the
         target: ``mutual_info_classif`` for a discrete target (integer, bool,
         or non-numeric labels, or floats that are all whole numbers), else
         ``mutual_info_regression``; seeded with ``random_state``.
       * ``rfe`` — recursive feature elimination: fit a linear estimator
         (``LogisticRegression`` for a discrete target, ``LinearRegression``
         otherwise), drop the feature with the smallest ``|coef|``, refit,
         until ``k`` remain.
    4. Keep the ``k`` best columns (ties resolved by original column order) in
       their original order.
    5. Return a DataSplitPayload whose arrays and partition manifests carry only
       the kept features.

Math:
    variance:
        score(j) = Var(X[:, j]) = E[(X_j - mu_j)^2]

    mutual information:
        MI(X_j; Y) = sum_{x,y} p(x,y) * log(p(x,y) / (p(x) * p(y)))
        estimated for continuous X_j with the k-nearest-neighbour estimator
        (Kraskov et al., 2004; Ross, 2014)

    rfe:
        repeat: fit w on the remaining features; drop argmin_j |w_j|
        until k features remain; kept features rank above every dropped one

References:
    - Kraskov, A., Stoegbauer, H., Grassberger, P. (2004). Estimating mutual
      information. *Physical Review E*, 69, 066138.
    - Ross, B.C. (2014). Mutual information between discrete and continuous
      data sets. *PLoS ONE*, 9(2), e87357.
    - Guyon, I., Weston, J., Barnhill, S., Vapnik, V. (2002). Gene selection for
      cancer classification using support vector machines. *Machine Learning*,
      46, 389-422.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.optional_dependency import OptionalDependency

from pirn_ml.types.data_split_payload import DataSplitPayload
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_arrays import SplitArrays
from pirn_ml.types.split_manifest import SplitManifest


class FeatureSelector(Knot):
    """Keep the ``k`` features that score best on the training partition."""

    valid_methods: ClassVar[frozenset[str]] = frozenset({"mutual_information", "variance", "rfe"})

    def __init__(
        self,
        *,
        split: Knot,
        k: Knot | int,
        method: Knot | str = "mutual_information",
        random_state: Knot | int = 0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split, k=k, method=method, random_state=random_state, _config=_config, **kwargs
        )

    async def process(
        self,
        split: DataSplitPayload,
        k: int,
        method: str = "mutual_information",
        random_state: int = 0,
        **_: Any,
    ) -> DataSplitPayload:
        """Score the training features with ``method`` and return the split reduced to the top k.

        Args:
            split: DataSplitPayload with train/test arrays and their manifests.
            k: Number of features to keep; 1 <= k <= feature count.
            method: One of ``valid_methods``.
            random_state: Seed for the mutual-information estimator.

        Returns:
            DataSplitPayload whose arrays and manifests carry only the kept
            features, in their original column order.

        Raises:
            TypeError: If split is not a DataSplitPayload, or k/random_state are not ints.
            ValueError: If k is out of range, method is unknown, the arrays do not
                match the feature names, or a target-based method has no ``y_train``.
        """
        if not isinstance(split, DataSplitPayload):
            raise TypeError("FeatureSelector: split must be a DataSplitPayload")
        if not isinstance(k, int):
            raise TypeError("FeatureSelector: k must be an int")
        if not isinstance(random_state, int):
            raise TypeError("FeatureSelector: random_state must be an int")
        if k < 1:
            raise ValueError("FeatureSelector: k must be >= 1")
        if method not in self.valid_methods:
            raise ValueError(f"FeatureSelector: method must be one of {sorted(self.valid_methods)}")
        feature_names = split.metadata.train.feature_names
        arrays = split.data
        feature_count = len(feature_names)
        if k > feature_count:
            raise ValueError(f"FeatureSelector: k={k} exceeds the {feature_count} features")
        for label, matrix in (("X_train", arrays.X_train), ("X_test", arrays.X_test)):
            if matrix.ndim != 2 or matrix.shape[1] != feature_count:
                raise ValueError(
                    f"FeatureSelector: {label} must be 2-D with {feature_count} columns "
                    f"(one per feature name), got shape {matrix.shape}"
                )
        if method != "variance" and arrays.y_train is None:
            raise ValueError(f"FeatureSelector: method '{method}' requires y_train")
        kept = await asyncio.to_thread(
            FeatureSelector._select, arrays.X_train, arrays.y_train, k, method, random_state
        )
        return FeatureSelector._reduce(split, kept, method)

    @staticmethod
    def _select(
        features: NDArray[Any],
        target: NDArray[Any] | None,
        k: int,
        method: str,
        random_state: int,
    ) -> list[int]:
        """Column indices of the k best features, in original column order."""
        matrix = np.asarray(features, dtype=np.float64)
        if method == "variance":
            scores = np.var(matrix, axis=0)
        elif target is None:
            raise ValueError(f"FeatureSelector: method '{method}' requires y_train")
        elif method == "mutual_information":
            scores = FeatureSelector._mutual_information(matrix, target, random_state)
        else:
            return FeatureSelector._recursive_elimination(matrix, target, k)
        # Stable sort on the negated score: equal scores keep column order.
        ranked = np.argsort(-scores, kind="stable")
        return sorted(int(column) for column in ranked[:k])

    @staticmethod
    def _mutual_information(
        matrix: NDArray[np.float64], target: NDArray[Any], random_state: int
    ) -> NDArray[np.float64]:
        feature_selection = OptionalDependency.require(
            "sklearn.feature_selection", extra="ml", package="pirn-ml"
        )
        if FeatureSelector._is_discrete(target):
            estimate: Any = feature_selection.mutual_info_classif(
                matrix, target, random_state=random_state
            )
        else:
            estimate = feature_selection.mutual_info_regression(
                matrix, np.asarray(target, dtype=np.float64), random_state=random_state
            )
        return np.asarray(estimate, dtype=np.float64)

    @staticmethod
    def _recursive_elimination(
        matrix: NDArray[np.float64], target: NDArray[Any], k: int
    ) -> list[int]:
        feature_selection = OptionalDependency.require(
            "sklearn.feature_selection", extra="ml", package="pirn-ml"
        )
        linear_model = OptionalDependency.require(
            "sklearn.linear_model", extra="ml", package="pirn-ml"
        )
        estimator: Any = (
            linear_model.LogisticRegression(max_iter=1000)
            if FeatureSelector._is_discrete(target)
            else linear_model.LinearRegression()
        )
        eliminator: Any = feature_selection.RFE(estimator, n_features_to_select=k, step=1)
        eliminator.fit(matrix, target)
        support = np.asarray(eliminator.support_, dtype=np.bool_)
        return [int(column) for column in np.flatnonzero(support)]

    @staticmethod
    def _is_discrete(target: NDArray[Any]) -> bool:
        """Whether the target holds class labels rather than a continuous quantity."""
        kind = target.dtype.kind
        if kind in "biuUSO":
            return True
        if kind == "f":
            values = np.asarray(target, dtype=np.float64)
            return bool(np.all(np.isfinite(values)) and np.all(np.mod(values, 1.0) == 0.0))
        return False

    @staticmethod
    def _reduce(split: DataSplitPayload, kept: list[int], method: str) -> DataSplitPayload:
        arrays = split.data
        manifest = split.metadata
        return DataSplitPayload(
            metadata=SplitManifest(
                train=FeatureSelector._reduce_manifest(manifest.train, kept, method),
                test=FeatureSelector._reduce_manifest(manifest.test, kept, method),
                validation=(
                    FeatureSelector._reduce_manifest(manifest.validation, kept, method)
                    if manifest.validation is not None
                    else None
                ),
            ),
            data=SplitArrays(
                X_train=arrays.X_train[:, kept],
                X_test=arrays.X_test[:, kept],
                y_train=arrays.y_train,
                y_test=arrays.y_test,
            ),
        )

    @staticmethod
    def _reduce_manifest(dataset: DatasetManifest, kept: list[int], method: str) -> DatasetManifest:
        return DatasetManifest(
            name=f"{dataset.name}:selected_{method}",
            feature_names=tuple(dataset.feature_names[column] for column in kept),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=dataset.fetched_at,
            row_indices=dataset.row_indices,
        )
