"""Data Engineering / Analytics Engineering knot library.

Install with::

    pip install 'pirn-data[data]'

Note: ``data_schema``, ``data_batch``, ``quality_check``, and
``quality_report`` are pure-Python contracts and remain importable in
minimal environments. Modules that touch pandas / pyarrow (sources,
transforms, sinks) import those dependencies lazily, so the
missing-dependency error fires only when those modules are imported.
"""

import warnings

from pirn.core.registry_visibility import RegistryVisibility
from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning

with warnings.catch_warnings(record=True) as _skip_warnings:
    warnings.simplefilter("always", SweetTeaWarning)
    Registry.fill_registry(module=__name__, library="pirn")
RegistryVisibility.log_skips(
    _skip_warnings,
    package=__name__,
    extra_hint=(
        "install the matching optional extra — see pyproject.toml "
        "[project.optional-dependencies], e.g. pirn-data[data]"
    ),
)

__all__: list[str] = []
