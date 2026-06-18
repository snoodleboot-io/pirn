"""ML Engineering / Data Science knot library.

Install with::

    pip install 'pirn-ml[ml]'

Note: the core orchestration layer (interfaces, types, data_prep,
features, training, evaluation, deployment) is pure-Python and
importable without optional ML dependencies. Modules that depend on
numpy / pandas / scikit-learn / pyarrow / joblib import those
dependencies lazily, so the missing-dependency error fires only when
those modules are imported.

``pirn-ml`` declares a hard dependency on ``pirn-data`` (ADR-3): the
dataset-loader knots consume ``DataBatch`` / ``LakehouseTable`` /
``FileSource`` / ``SqlSource`` from ``pirn_data``.
"""

import warnings

from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SweetTeaWarning)
    Registry.fill_registry(module=__name__, library="pirn")

__all__: list[str] = []
