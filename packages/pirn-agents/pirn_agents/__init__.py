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

import importlib
import logging
import re
import warnings

from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning

from pirn_agents.capability_probe import CapabilityProbe


class _RegistryVisibility:
    """Re-emit sweet_tea's swallowed skip-warnings through the package logger.

    ``Registry.fill_registry`` warns-and-skips any module whose import raises
    ``ImportError``/``ModuleNotFoundError`` — the mechanism that lets an
    optional dependency be genuinely optional (PIR-856). This package used to
    suppress that warning outright (``simplefilter("ignore", SweetTeaWarning)``),
    which meant a module silently dropped out of YAML name resolution with no
    trace anywhere. This captures the warnings sweet_tea already raises and
    re-emits one WARNING-level log line per skipped module — naming the module
    and, best-effort, the underlying import error — while keeping import of
    this package itself non-fatal.
    """

    @staticmethod
    def log_skips(records: list[warnings.WarningMessage], *, package: str, extra_hint: str) -> None:
        logger = logging.getLogger(package)
        for record in records:
            if not issubclass(record.category, SweetTeaWarning):
                continue
            match = re.match(
                r"^Skipping module (?P<module>\S+) due to missing optional dependency$",
                str(record.message),
            )
            if match is None:
                continue
            module_name = match.group("module")
            detail = "unknown import error"
            try:
                importlib.import_module(module_name)
            except ImportError as exc:
                detail = str(exc)
            logger.warning(
                "%s: knot module %s skipped — %s; %s",
                package,
                module_name,
                detail,
                extra_hint,
            )


with warnings.catch_warnings(record=True) as _skip_warnings:
    warnings.simplefilter("always", SweetTeaWarning)
    Registry.fill_registry(module=__name__, library="pirn")
_RegistryVisibility.log_skips(
    _skip_warnings,
    package=__name__,
    extra_hint=(
        "install the matching optional extra — see pyproject.toml "
        "[project.optional-dependencies], e.g. pirn-agents[llm], "
        "pirn-agents[vector], or pirn-agents[all]"
    ),
)

available_extras = CapabilityProbe().available_extras
