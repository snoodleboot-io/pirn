"""Data Engineering / Analytics Engineering knot library.

Install with::

    pip install 'pirn[data]'

Note: ``data_schema``, ``data_batch``, ``quality_check``, and
``quality_report`` are pure-Python contracts and remain importable in
minimal environments. Modules that touch pandas / pyarrow (sources,
transforms, sinks) instantiate :class:`pirn.domains.extras_loader.ExtrasLoader`
at module top so the missing-extras error fires only when those modules
are imported.

See ``planning/current/domain-knot-libraries-prd.md`` for the full catalog.
"""

__all__: list[str] = []
