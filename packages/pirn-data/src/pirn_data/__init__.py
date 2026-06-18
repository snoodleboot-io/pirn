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

from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SweetTeaWarning)
    Registry.fill_registry(module=__name__, library="pirn")

__all__: list[str] = []
