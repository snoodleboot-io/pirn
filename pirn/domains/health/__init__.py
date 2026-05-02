"""Healthcare / Genomics / Imaging / EEG-MEG / Wearables / Pathology / Trials.

The health domain provides an orchestration surface for clinical and
biomedical pipelines built from pirn ``Knot`` units of work. Sub-areas:

* :mod:`pirn.domains.health.clinical` — FHIR / OMOP / clinical NLP knots
* :mod:`pirn.domains.health.genomics` — sequencing / variants / expression
* :mod:`pirn.domains.health.mri` — DICOM / NIfTI / volumetrics
* :mod:`pirn.domains.health.eeg_meg` — EEG / MEG signal pipelines
* :mod:`pirn.domains.health.wearables` — ECG / HRV / sleep / glucose
* :mod:`pirn.domains.health.pathology` — WSI tile / cell / mitosis
* :mod:`pirn.domains.health.trials` — SDTM / ADaM / define-XML / MedDRA

Heavy SDKs (``pydicom``, ``mne``, ``nibabel``, ``pyfaidx``, ``pysam``,
``fhir.resources``) are **not** imported at package load time. The
orchestration knots ship as importable stubs so the surface is usable
without installing the optional extra. To run real algorithm bodies,
install with::

    pip install 'pirn[health]'

and replace the stub ``process()`` bodies with vendor SDK calls in your
own subclasses (or wait for the production implementations to land).
"""


__all__: list[str] = []
