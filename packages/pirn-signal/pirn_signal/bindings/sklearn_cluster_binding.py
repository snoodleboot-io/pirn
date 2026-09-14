"""``SklearnClusterBinding`` — typed boundary over ``sklearn.cluster``.

scikit-learn ships no type stubs. This binding performs the lazy optional-extra
import and exposes k-means labelling with real ``NDArray`` annotations.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

import numpy as np
from numpy.typing import NDArray

from pirn_signal.signal_optional_dependency import SignalOptionalDependency


class SklearnClusterBinding:
    """Annotated facade over the ``sklearn.cluster`` estimators used by pirn-signal knots."""

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    @classmethod
    def load(cls) -> SklearnClusterBinding:
        """Import ``sklearn.cluster`` lazily through :class:`SignalOptionalDependency`.

        Returns:
            A binding over the imported module.

        Raises:
            ImportError: If ``sklearn.cluster`` is not installed; the message names
                ``pirn-signal[separation]``.
        """
        return cls(SignalOptionalDependency.require("sklearn.cluster", extra="separation"))

    def kmeans_labels(
        self, samples: NDArray[np.floating[Any]], cluster_count: int
    ) -> NDArray[np.int_]:
        """Cluster ``samples`` (``(n_samples, n_features)``) with seeded k-means; return labels."""
        estimator: Any = self._module.KMeans(
            n_clusters=cluster_count, random_state=0, n_init="auto"
        )
        labels: NDArray[np.int_] = np.asarray(estimator.fit_predict(samples), dtype=np.int_)
        return labels
