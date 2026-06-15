"""Oil & Gas knot library.

The orchestration knots ship as slim stubs that validate inputs and
return typed result values. Production deployments that read SEG-Y or
LAS payloads must install the optional extras::

    pip install 'pirn-oilgas[oilgas]'

Without the extras the orchestration graph still imports, type-checks,
and unit-tests; only the knots that need the real SDKs at runtime fail.
Concrete backends instantiate
:class:`pirn_oilgas.extras_loader.ExtrasLoader` at the call boundary so
the missing-extras error fires only when a real implementation is used.
"""

import warnings

from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SweetTeaWarning)
    Registry.fill_registry(module=__name__, library="pirn")

__all__: list[str] = []
