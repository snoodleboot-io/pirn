"""``RegistryVisibility`` — re-emit sweet_tea's swallowed skip-warnings as log lines.

``Registry.fill_registry`` warns-and-skips any module whose import raises
``ImportError``/``ModuleNotFoundError`` — the mechanism that lets an optional
dependency be genuinely optional (PIR-856). A package that suppresses that
warning (``simplefilter("ignore", SweetTeaWarning)``) lets a module drop out of
YAML name resolution with no trace anywhere. This captures the warnings
sweet_tea already raises and re-emits one WARNING-level log line per skipped
module — naming the module and, best-effort, the underlying import error —
while keeping import of the calling package non-fatal.

Every distribution in the workspace calls ``fill_registry`` from its
``__init__`` and needs this. It lived as a private ``_RegistryVisibility``
copied verbatim into all seven of them, so a fix to the regex or the log line
had to be made seven times, and six of the copies were byte-identical
(PIR-873). It lives in core once instead; each package passes its own
``package`` name and install hint.

Usage, from a package ``__init__``::

    with warnings.catch_warnings(record=True) as skipped:
        warnings.simplefilter("always", SweetTeaWarning)
        Registry.fill_registry(module=__name__, library="pirn")
    RegistryVisibility.log_skips(
        skipped, package=__name__, extra_hint="install pirn-signal[signal]"
    )
"""

from __future__ import annotations

import importlib
import logging
import re
import warnings
from typing import ClassVar

from sweet_tea.sweet_tea_warning import SweetTeaWarning


class RegistryVisibility:
    """Turn sweet_tea's skip warnings into log lines naming the module and the cause."""

    #: The warning text ``fill_registry`` raises for a module it skipped. Matched
    #: rather than parsed loosely so an unrelated ``SweetTeaWarning`` is left alone.
    _skip_message: ClassVar[re.Pattern[str]] = re.compile(
        r"^Skipping module (?P<module>\S+) due to missing optional dependency$"
    )

    @staticmethod
    def log_skips(records: list[warnings.WarningMessage], *, package: str, extra_hint: str) -> None:
        """Log one WARNING per module ``fill_registry`` skipped.

        Args:
            records: The warnings captured around the ``fill_registry`` call.
            package: The importing package's name; it names the logger and
                appears in each line.
            extra_hint: The install hint for this distribution's extras.
        """
        logger = logging.getLogger(package)
        for record in records:
            if not issubclass(record.category, SweetTeaWarning):
                continue
            match = RegistryVisibility._skip_message.match(str(record.message))
            if match is None:
                continue
            module_name = match.group("module")
            logger.warning(
                "%s: knot module %s skipped — %s; %s",
                package,
                module_name,
                RegistryVisibility._import_error(module_name),
                extra_hint,
            )

    @staticmethod
    def _import_error(module_name: str) -> str:
        """Return why ``module_name`` cannot be imported, best-effort.

        sweet_tea's warning names the module but not the cause, so the import is
        retried here purely to recover the message. A module that imports fine
        on the retry (a transient or ordering problem) leaves the cause unknown
        rather than claiming one.
        """
        try:
            importlib.import_module(module_name)
        except ImportError as exc:
            return str(exc)
        return "unknown import error"
