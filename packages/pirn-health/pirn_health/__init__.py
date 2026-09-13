"""Healthcare / Genomics / Imaging / EEG-MEG / Wearables / Pathology / Trials.

The health domain provides an orchestration surface for clinical and
biomedical pipelines built from pirn ``Knot`` units of work. Sub-areas:

* :mod:`pirn_health.clinical` — FHIR / OMOP / clinical NLP knots
* :mod:`pirn_health.genomics` — sequencing / variants / expression
* :mod:`pirn_health.mri` — DICOM / NIfTI / volumetrics
* :mod:`pirn_health.eeg_meg` — EEG / MEG signal pipelines
* :mod:`pirn_health.wearables` — ECG / HRV / sleep / glucose
* :mod:`pirn_health.pathology` — WSI tile / cell / mitosis
* :mod:`pirn_health.trials` — SDTM / ADaM / define-XML / MedDRA

Heavy SDKs (``pydicom``, ``mne``, ``nibabel``, ``pyfaidx``, ``pysam``,
``fhir.resources``) are **not** imported at package load time. The
orchestration knots ship as importable stubs so the surface is usable
without installing the optional extra. To run real algorithm bodies,
install with::

    pip install 'pirn-health[health]'

and replace the stub ``process()`` bodies with vendor SDK calls in your
own subclasses (or wait for the production implementations to land).
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
        "[project.optional-dependencies], e.g. pirn-health[health]"
    ),
)

__all__: list[str] = []
