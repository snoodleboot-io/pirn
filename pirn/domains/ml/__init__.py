"""ML Engineering / Data Science knot library.

Install with::

    pip install 'pirn[ml]'

Note: the core orchestration layer (interfaces, types, data_prep,
features, training, evaluation, deployment) is pure-Python and
importable without optional ML dependencies. Modules that depend on
numpy / pandas / scikit-learn / pyarrow / joblib instantiate
:class:`pirn.domains.extras_loader.ExtrasLoader` at module top so the
missing-extras error fires only when those modules are imported.

See ``planning/current/domain-knot-libraries-prd.md`` for the full catalog.
"""

__all__: list[str] = []
