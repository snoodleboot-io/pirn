"""Oil & Gas knot library.

The orchestration knots ship as slim stubs that validate inputs and
return typed result values. Production deployments that read SEG-Y or
LAS payloads must install the optional extras::

    pip install 'pirn-oilgas[oilgas]'

Without the extras the orchestration graph still imports, type-checks,
and unit-tests; only the knots that need the real SDKs at runtime fail.
Concrete backends import their optional dependencies lazily (at the call
boundary), so the missing-dependency error fires only when a real
implementation is used.
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
        "[project.optional-dependencies], e.g. pirn-oilgas[oilgas]"
    ),
)

__all__: list[str] = []
