"""Healthcare / Genomics / Imaging / EEG-MEG / Wearables / Pathology / Trials.

Install with::

    pip install 'pirn[health]'
"""

from pirn.domains.extras_loader import ExtrasLoader


ExtrasLoader(
    "health",
    [
        "pydicom",   # DICOM medical imaging
        "mne",       # EEG / MEG processing
        "nibabel",   # NIfTI / neuroimaging
        "pyfaidx",   # FASTA / genomics
    ],
).require()


__all__: list[str] = []
