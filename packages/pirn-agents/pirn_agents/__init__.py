"""Agentic Pipelines / Patterns knot library.

Install with::

    pip install pirn-agents

The agents domain has no heavy core dependencies — concrete LLM, memory,
and tool providers are user-supplied through interfaces defined in this
domain. Importing this package self-registers every ``Knot`` subclass in
the tree with the shared registry via
``sweet_tea.registry.Registry.fill_registry()`` so the knots become
resolvable by name through
:class:`sweet_tea.abstract_inverter_factory.AbstractInverterFactory`.

The fill is eager on purpose (PIR-780). Walking and importing the whole tree
costs ~0.14 s of the ~2.2 s import; the other ~1.4 s is sweet_tea's
``Registry.register`` checking for duplicates with ``new_entry not in
cls.__registry``, a linear scan of pydantic models that is quadratic in the
size of the process-wide registry. A manifest-driven or lazy fill would trade
a build step and a staleness risk for the small share, and leave the large one
untouched, so neither was built. ``tests/test_import_cost.py`` bounds both.

See ``planning/current/domain-knot-libraries-prd.md`` for the full catalog.
"""

import warnings

from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning

from pirn_agents.capability_probe import CapabilityProbe

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SweetTeaWarning)
    Registry.fill_registry(module=__name__, library="pirn")

available_extras = CapabilityProbe().available_extras
