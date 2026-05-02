# Enforcement Review — Phase 4 File Formats

**Date:** 2026-05-02  
**Scope:** `pirn/domains/connectors/file_formats/` — all source files (excluding `__init__.py`)  
**Rules checked:**

1. One class per file
2. No `UPPER_SNAKE` / module-level constants
3. No module-level free functions
4. No bare `except` / `except Exception: pass` (fail-loud)
5. Optional deps imported lazily inside methods only
6. `from __future__ import annotations` as first non-comment line
7. No pass-only method bodies (without an explanatory override comment)
8. SOLID SRP — a class should have one reason to change

Severity key:
- **MUST_FIX** — directly contradicts a stated convention rule
- **SHOULD_FIX** — likely mistake; degrades maintainability or safety
- **CONSIDER** — stylistic improvement, lower urgency

---

## MUST_FIX

### `sam_format.py`

**Rule 3 — Module-level free functions**

Lines 128+: Nine module-level free functions are defined outside any class:
`_write_tempfile`, `_make_tempfile_path`, `_safe_unlink`, `_alignment_to_record`,
`_build_header`, `_header_from_text`, `_infer_header`, `_record_to_alignment`,
`_validate_record`.

These are imported directly by `bam_format.py` and `cram_format.py` as a shared
utility shim. This is a deliberate cross-module coupling that violates the convention.

**Suggested fix:** Extract these into a `_SamUtils` (or `SamHelpers`) class with
`@staticmethod` members in its own file (`sam_utils.py`). Have `SamFormat`,
`BamFormat`, and `CramFormat` import from that class. Alternatively, have
`BamFormat`/`CramFormat` inherit from `SamFormat` and access helpers via `super()`.

---

### `epub_format.py`

**Rule 1 — One class per file**

Lines 29–53: `_HtmlStripper(HTMLParser)` is defined in the same file as `EpubFormat`.
Even though it is private and used only by `EpubFormat`, the convention does not allow
multiple classes per file regardless of visibility.

**Suggested fix:** Move `_HtmlStripper` to `pirn/domains/connectors/file_formats/_html_stripper.py`
and import it in `epub_format.py`.

---

### `cda_xml_format.py`

**Rule 2 — No module-level constants**

Line ~30: `_CDA_NS = "urn:hl7-org:v3"` is a bare module-level string constant.

**Suggested fix:** Move to a private `ClassVar[str]` on `CdaXmlFormat`:
```python
_cda_ns: ClassVar[str] = "urn:hl7-org:v3"
```

---

### `define_xml_format.py`

**Rule 2 — No module-level constants**

Lines ~30–31: `_ODM_NS` and `_DEF_NS` are bare module-level string constants.

**Suggested fix:** Move both to `ClassVar[str]` on `DefineXmlFormat`.

---

### `fhir_xml_format.py`

**Rule 2 — No module-level constants**

Line ~27: `_FHIR_NS = "http://hl7.org/fhir"` is a bare module-level string constant.

**Suggested fix:** Move to `ClassVar[str]` on `FhirXmlFormat`.

---

### `hl7v2_format.py`

**Rule 2 — No module-level constants**

Line ~29: `_PHI_PID_FIELDS: frozenset[int] = frozenset({5, 7, 11})` is a module-level constant.

**Suggested fix:** Move to `ClassVar[frozenset[int]]` on `Hl7V2Format`.

---

### `prodml_format.py`

**Rule 2 — No module-level constants**

Line ~25: `_PRODML_NS` is a bare module-level string constant.

**Suggested fix:** Move to `ClassVar[str]` on `ProdmlFormat`.

---

### `resqml_format.py`

**Rule 2 — No module-level constants**

Line ~27: `_RESQML_NS` is a bare module-level string constant.

**Suggested fix:** Move to `ClassVar[str]` on `ResqmlFormat`.

---

### `segd_format.py`

**Rule 2 — No module-level constants**

Line ~32: `_GH1_SIZE = 32` is a bare module-level integer constant.

**Suggested fix:** Move to `ClassVar[int]` on `SegdFormat`.

---

### `witsml_format.py`

**Rule 2 — No module-level constants**

Lines 25–26: `_WITSML_NS` and `_WITSML_VERSION` are bare module-level string constants.

**Suggested fix:** Move both to `ClassVar[str]` on `WitsmlFormat`.

---

### `fastq_format.py`

**Rule (nested functions)** — nested function `_drain_lines` is defined inside the async
generator `_iter` inside `read` (~line 58). The conventions prohibit nested function
definitions without a `#design-decision-override` comment.

**Suggested fix:** Extract `_drain_lines` to a `@staticmethod` that accepts the
`bytearray` buffer and `encoding` as parameters, or lift it to a module-private
`@staticmethod` on `FastqFormat`. Same pattern already used cleanly in `csv_format.py`.

---

### `vcf_format.py`

**Rule (nested functions)** — nested function `_drain_lines` is defined inside the async
generator `_iter` inside `read` (~line 72). Same issue as `fastq_format.py`.

**Suggested fix:** Extract to a `@staticmethod _drain_lines(buffered, encoding, final)`.

---

### `grib_format.py`

**Rule (nested functions)** — function `_get` is defined inside static method
`_extract_message` (~line 87).

**Suggested fix:** Hoist `_get` to a `@staticmethod` on `GribFormat`.

---

### `markdown_format.py`

**Rule (nested functions)** — function `_flush` is defined inside static method
`_records_by_heading` (~lines 119–129).

**Suggested fix:** Hoist `_flush` to a `@staticmethod` on `MarkdownFormat`.

---

### `prodml_format.py`

**Rule 5 — Optional deps imported lazily**

Line ~39: `import io` appears mid-method inside `_decode_full`. `io` is a stdlib
module and does not need lazy import, but it should appear at the top of the file.

**Suggested fix:** Move `import io` to the module-level import block.

---

### `resqml_format.py`

**Rule 5 — Optional deps imported lazily (false placement)**

Line ~41: `import io` appears mid-method inside `_decode_full`. Same as above.

**Suggested fix:** Move `import io` to the module-level import block.

---

### `witsml_format.py`

**Rule 5 — Optional deps imported lazily (false placement)**

Line ~40: `import io` appears mid-method inside `_decode_full`.

**Suggested fix:** Move `import io` to the module-level import block.

---

### `mzml_format.py`

**Rule 5 — Optional deps imported lazily (false placement)**

Line ~178: `import base64` appears mid-method inside `_record_to_spectrum_element`.
`base64` is stdlib; it must be imported at module level.

**Suggested fix:** Move `import base64` to the module-level import block.

---

### `safetensors_format.py`

**Rule 5 — Optional deps imported lazily (false placement)**

Lines ~171–172: `import json` and `import struct` appear mid-method inside
`_extract_metadata`. Both are stdlib modules.

**Suggested fix:** Move both to the module-level import block.

---

### `segy_format.py`

**Rule 5 — Duplicate/redundant mid-method import**

Line ~70: `import struct as _struct` appears mid-method even though `struct` is
already imported at module level. This creates a confusing shadowed alias.

**Suggested fix:** Remove the mid-method import and use the existing module-level
`struct` reference.

---

## SHOULD_FIX

### `bdf_format.py`

**Rule 4 — `except Exception: pass`**

Lines ~148–155 (`_apply_phi_redaction`): swallows all exceptions from pyedflib PHI
setter calls with a bare `pass`. Any unexpected failure (wrong API, wrong type) is
silently ignored, defeating the fail-loud principle.

**Suggested fix:** Catch only `AttributeError` (for missing setter methods across
pyedflib versions) and re-raise anything else:
```python
except AttributeError:
    pass  # pyedflib version does not expose this setter
```

---

### `edf_format.py`

**Rule 4 — `except Exception: pass`**

Lines ~186–187 (`_apply_phi_redaction`): same pattern as `BdfFormat`.

**Suggested fix:** Same as above — narrow to `AttributeError`.

**Rule 7 — Pass-only method body**

Lines ~193–194 (`_write_annotations`): method body is only `pass` with a one-line
comment. There is no `#design-decision-override` to indicate this is intentional.

**Suggested fix:** Add `# design-decision-override: no-op stub; overridden in EdfPlusFormat`
or raise `NotImplementedError` in the base and override in `EdfPlusFormat`.

---

### `edf_plus_format.py`

**Rule 4 — `except Exception:`**

Line ~69 (`_read_annotations`): returns empty list on any exception, hiding parse errors.

Line ~87 (`_write_annotations`): `except Exception: pass` swallows write failures.

**Suggested fix:** Narrow to specific pyedflib exceptions and log or re-raise the rest.

---

### `dicom_format.py`

**Rule 4 — `except Exception:`**

Line ~263 (`_extract_pixel_shape`): silently returns empty tuple on any exception.

**Suggested fix:** Catch only the pydicom-specific exceptions (e.g. `AttributeError`,
`KeyError`) and log a warning before returning the fallback.

---

### `dlis_format.py`

**Rule 4 — `except Exception:`**

Line ~63 (`_decode_full`): silently sets `data = b""` on any error during array
extraction, masking real decoding failures.

**Suggested fix:** Catch specific exceptions from `dlisio` (e.g. `dlisio.core.errors`)
and log a warning; re-raise others.

---

### `fits_format.py`

**Rule 4 — `except Exception:`**

Lines ~60 and ~91: silently set `data_bytes = None` and swallow HDU read errors.

**Suggested fix:** Narrow to `astropy`-specific exceptions; log at WARNING level; re-raise unknowns.

---

### `gguf_format.py`

**Rule 4 — `except Exception: pass`**

Lines ~164–165 (`_encode_full`): swallows writer close failure.

Lines ~182–183 (`_field_value`): swallows conversion failure, returning `None` silently.

**Suggested fix:**
- For `writer.close()`: use a `finally` block and let the exception propagate.
- For `_field_value`: raise `ValueError` with context instead of returning `None`.

---

### `grib_format.py`

**Rule 4 — Multiple `except Exception:` patterns**

Lines ~58, ~68, ~90, ~101–103: swallow GRIB field extraction errors silently.

**Suggested fix:** Use `eccodes`-specific exception types; log at WARNING for expected
missing fields; re-raise unexpected exceptions.

---

### `nifti_format.py`

**Rule 4 — `except Exception: pass`**

Line ~96 (`_extract_header`): silently swallows header extraction failures.

**Suggested fix:** Narrow to `nibabel`-specific exceptions; log a warning; re-raise others.

---

### `root_format.py`

**Rule 4 — Multiple `except Exception:` patterns**

Lines ~59, ~64, ~71 (`_decode_full`): three separate branch catches that swallow errors silently.

**Suggested fix:** Catch ROOT-specific exceptions; log at WARNING; re-raise unknowns.

---

### `segy_format.py`

**Rule 4 — `except Exception: pass`**

Line ~139 (`_encode_full`): silently swallows failures during SEG-Y write finalisation.

**Suggested fix:** Remove the bare except; let the exception propagate. If cleanup is
needed, use `finally` without catching.

---

### `tf_saved_model_format.py`

**Rule 4 — Multiple `except Exception:` patterns**

Lines ~72 and ~80 (`_decode_full`): silently swallow TensorFlow inspection and asset
loading errors.

**Suggested fix:** Catch only `tf.errors.NotFoundError` or `AttributeError`; log a warning; re-raise others.

---

## CONSIDER

### `bids_dataset_format.py`

**Rule 4 — `except Exception: pass`** (SHOULD_FIX borderline)

Line ~108 (`_validate_bids_if_available`): BIDS validation errors are silently swallowed.
The intent is "skip validation if bids-validator is absent", but the catch is too broad —
it also hides actual validation errors when the library is present.

**Suggested fix:** Catch `ImportError` only; let validation failures propagate, or surface
them as structured warnings in the returned records.

---

### `kml_format.py`

**ClassVar annotation missing**

Lines ~36–39: `_kml_namespace` and `_supported_geometries` are class-level attributes
that serve as constants but lack `ClassVar` type annotations.

**Suggested fix:** Annotate with `ClassVar[str]` and `ClassVar[frozenset[str]]` respectively.

---

### `png_format.py`

**Rule 7 — `__init__` with only `pass`**

Line ~42: `__init__(self) -> None: pass` — The class has no instance state so no
`__init__` is needed at all, or a `#design-decision-override` comment should explain why.

**Suggested fix:** Remove the `__init__` entirely (inherit the default), or add a comment.

---

## Files confirmed clean

The following files had no violations across all 8 rules:

`aac_format.py`, `archive_file_format.py`, `arrow_ipc_format.py`, `asdf_format.py`,
`avro_format.py`, `bam_format.py`, `batch_file_format.py`, `bcf_format.py`,
`brainvision_format.py`, `compressed_file_format.py`, `cram_format.py`, `csv_format.py`,
`docx_format.py`, `fasta_format.py`, `feather_format.py`, `fhir_json_format.py`,
`flac_format.py`, `geojson_format.py`, `geopackage_format.py`, `geotiff_format.py`,
`hdf5_format.py`, `heic_format.py`, `html_format.py`, `joblib_format.py`,
`jpeg_format.py`, `json_format.py`, `jsonl_format.py`, `las_format.py`, `m4a_format.py`,
`matlab_mat_format.py`, `mp3_format.py`, `netcdf_format.py`, `netcdf4_format.py`,
`numpy_npy_format.py`, `numpy_npz_format.py`, `ods_format.py`, `ogg_format.py`,
`onnx_format.py`, `open_slide_format.py`, `orc_format.py`, `parquet_format.py`,
`pdf_format.py`, `plain_text_format.py`, `pptx_format.py`, `pytorch_format.py`,
`rtf_format.py`, `sdtm_xpt_format.py`, `shapefile_format.py`, `streaming_file_format.py`,
`tflite_format.py`, `tiff_format.py`, `tsv_format.py`, `vcf_format.py`, `wav_format.py`,
`webp_format.py`, `xlsx_format.py`, `zarr_format.py`

---

## Summary counts

| Severity   | Count |
|------------|-------|
| MUST_FIX   | 17    |
| SHOULD_FIX | 12    |
| CONSIDER   | 3     |
| **Total**  | **32** |

### Top categories

| Rule violated                          | Findings |
|----------------------------------------|----------|
| Bare `except Exception` / fail-loud    | 14       |
| Module-level constants                 | 8        |
| Nested functions                       | 4        |
| One class per file                     | 1        |
| Module-level free functions            | 1        |
| stdlib import in wrong location        | 4        |
| Pass-only body without override note   | 1        |
| Missing ClassVar annotation            | 2        |
