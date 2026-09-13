"""pirn — a pipeline framework where everything is a knot.

Knot discovery
--------------
At import time, pirn calls :meth:`sweet_tea.registry.Registry.fill_registry`
over its own package tree. Every :class:`pirn.core.knot.Knot` subclass shipped
with pirn is auto-registered under ``library="pirn"`` with the lowercase
class name as its registry key (CamelCase, snake_case, and no-underscore
variations all resolve to the same entry through sweet_tea's
:meth:`BaseFactory._generate_key_variations`).

This means YAML pipelines can reference any built-in pirn knot by name
without ``import`` boilerplate::

    nodes:
      - id: read
        callable: object_store_read_source

YAML name resolution goes through
:class:`sweet_tea.abstract_inverter_factory.AbstractInverterFactory[Knot]`
— sweet_tea's typed factory that returns the class definition (rather than
instantiating it), so the loader can supply construction kwargs later.

User projects: register your own knots
--------------------------------------
If you define your own :class:`Knot` subclasses outside the pirn package
(e.g. ``my_company.transforms.NormaliseAddresses``), call
:meth:`Registry.fill_registry` from **your** project's package init so your
classes are auto-discovered too::

    # my_company/__init__.py
    from sweet_tea.registry import Registry

    Registry.fill_registry()  # scans my_company/ and registers every class

After that, your knots are resolvable by name from YAML pipelines just like
pirn's built-ins. To restrict resolution to your library only, look up via
``AbstractInverterFactory[Knot].create(name, library="my_company")``.
"""

import importlib
import logging
import re
import warnings
from importlib.metadata import PackageNotFoundError, version

from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning


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
    Registry.fill_registry()
_RegistryVisibility.log_skips(
    _skip_warnings,
    package=__name__,
    extra_hint=(
        "install the matching optional extra — see pyproject.toml "
        "[project.optional-dependencies], or pirn-core[all] for everything"
    ),
)

try:
    # Core ships as the ``pirn-core`` distribution but imports as ``pirn``.
    __version__ = version("pirn-core")
except PackageNotFoundError:
    __version__ = "unknown"

# No public-API re-exports here (PIR-744). The house convention forbids import
# forwarding (``.claude/conventions/languages/python.md``), enforced workspace-wide
# by ``scripts/check_no_import_forwarding.py``. Import framework primitives from the
# module that owns them, e.g. ``from pirn.tapestry import Tapestry``,
# ``from pirn.core.knot import Knot``, ``from pirn.core.run_request import RunRequest``.
