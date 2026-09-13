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

import importlib
import logging
import re
import warnings

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
    Registry.fill_registry(module=__name__, library="pirn")
_RegistryVisibility.log_skips(
    _skip_warnings,
    package=__name__,
    extra_hint=(
        "install the matching optional extra — see pyproject.toml "
        "[project.optional-dependencies], e.g. pirn-ml[ml]"
    ),
)

__all__: list[str] = []
