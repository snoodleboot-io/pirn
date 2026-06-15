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

import warnings

from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SweetTeaWarning)
    Registry.fill_registry(module=__name__, library="pirn")

__all__: list[str] = []
