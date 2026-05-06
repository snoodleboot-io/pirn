# Contributing a New Domain Knot (File Format)

This guide walks through adding a new file format to `pirn.domains.connectors.file_formats`. By the end you will have a format class, passing tests, a registered export, and an optional extra in `pyproject.toml`.

---

## Before You Start

Check the existing format list in [`docs/connectors/index.md`](../connectors/index.md). If the format you want to add is already there, consider opening a bug report instead.

Read and follow every convention here — these are enforced by CI:

- One class per file, no exceptions.
- No module-level constants. Configuration lives as `ClassVar` attributes or constructor parameters.
- No `Protocol` — use abstract base classes.
- Methods belong to classes; no module-level functions (use `@staticmethod` inside the class instead).
- No nested function definitions that can be expressed as a `@staticmethod`.
- No bare `except:` — always catch a specific exception type.
- All constructor parameter validation is explicit (type check then value check; raise `TypeError` before `ValueError`).

**See also:** General Conventions (see `.claude/conventions/core/general.md` in the repository root)

---

## Step 1 — Choose BatchFileFormat or StreamingFileFormat

| Question | Answer → use |
|----------|-------------|
| Does the library require the entire file in memory before it can start decoding? | `BatchFileFormat` |
| Does the format have a footer (Parquet, FITS) or requires random access (HDF5, XLSX, ZIP)? | `BatchFileFormat` |
| Can records be decoded and emitted one-at-a-time from a byte stream? | `StreamingFileFormat` |
| Is this a line-oriented text format (CSV, FASTQ, SAM) or a framed binary (Arrow IPC)? | `StreamingFileFormat` |

Both bases live in `pirn.domains.connectors.file_formats`:

```
batch_file_format.py      → BatchFileFormat
streaming_file_format.py  → StreamingFileFormat
```

When in doubt, use `BatchFileFormat`. It is always correct (at the cost of memory); `StreamingFileFormat` is an optimisation.

---

## Step 2 — Implement the Format Class

### BatchFileFormat (worked example)

Create one file: `pirn/domains/connectors/file_formats/widget_format.py`

```python
"""``WidgetFormat`` — Widget binary format encoder/decoder.

Requires the ``widgetlib`` package.

Install: ``pip install pirn[widget]``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class WidgetFormat(BatchFileFormat):
    """Widget binary format backed by ``widgetlib``.

    Args:
        schema_version: Widget schema version to target. Defaults to ``2``.
    """

    _supported_versions: ClassVar[frozenset[int]] = frozenset({1, 2, 3})

    def __init__(self, schema_version: int = 2) -> None:
        if not isinstance(schema_version, int) or isinstance(
            schema_version, bool
        ):
            raise TypeError(
                "WidgetFormat: schema_version must be int"
            )
        if schema_version not in self._supported_versions:
            raise ValueError(
                "WidgetFormat: schema_version must be one of "
                f"{sorted(self._supported_versions)}, got {schema_version!r}"
            )
        self._schema_version = schema_version

    @property
    def name(self) -> str:
        return "widget"

    @property
    def schema_version(self) -> int:
        return self._schema_version

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        try:
            import widgetlib  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "WidgetFormat requires 'widgetlib'. "
                "Install via `pip install pirn[widget]`."
            ) from exc
        widgets = widgetlib.load(payload, version=self._schema_version)
        return [{"id": w.id, "value": w.value} for w in widgets]

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        try:
            import widgetlib  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "WidgetFormat requires 'widgetlib'. "
                "Install via `pip install pirn[widget]`."
            ) from exc
        widgets = [
            widgetlib.Widget(id=r["id"], value=r["value"]) for r in records
        ]
        return widgetlib.dump(widgets, version=self._schema_version)
```

Key rules illustrated above:

1. `_supported_versions` is a `ClassVar` using `lower_snake` — not an uppercase module constant.
2. `widgetlib` is imported inside the method body (`lazy import pattern`) — the module can be imported even if `widgetlib` is not installed.
3. The `ImportError` message tells the user exactly which extra to install.
4. Constructor validates type before value (raises `TypeError` before `ValueError`).
5. `bool` is explicitly excluded from the `int` check because `isinstance(True, int)` is `True` in Python.

### StreamingFileFormat (worked example)

For line-oriented or framed formats implement `read` and `write` directly:

```python
"""``WidgetTextFormat`` — newline-delimited Widget text format.

No optional dependency — stdlib only.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Mapping

from pirn.domains.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)


class WidgetTextFormat(StreamingFileFormat):
    """Newline-delimited ``id=value`` Widget text format.

    Args:
        encoding: Text encoding. Defaults to ``"utf-8"``.
    """

    def __init__(self, encoding: str = "utf-8") -> None:
        if not isinstance(encoding, str):
            raise TypeError("WidgetTextFormat: encoding must be str")
        if not encoding:
            raise ValueError("WidgetTextFormat: encoding must be non-empty")
        self._encoding = encoding

    @property
    def name(self) -> str:
        return "widget_text"

    @property
    def encoding(self) -> str:
        return self._encoding

    async def read(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[Mapping[str, Any]]:
        encoding = self._encoding

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            payload = await WidgetTextFormat._drain_all(body)
            for line in payload.decode(encoding).splitlines():
                line = line.strip()
                if not line:
                    continue
                key, _, value = line.partition("=")
                yield {"id": key.strip(), "value": value.strip()}

        return _iter()

    async def write(
        self, records: AsyncIterator[Mapping[str, Any]]
    ) -> AsyncIterator[bytes]:
        encoding = self._encoding

        async def _iter() -> AsyncIterator[bytes]:
            async for record in records:
                line = f"{record['id']}={record['value']}\n"
                yield line.encode(encoding)

        return _iter()

    @staticmethod
    async def _drain_all(body: AsyncIterator[bytes]) -> bytes:
        chunks: list[bytes] = []
        async for chunk in body:
            chunks.append(chunk)
        return b"".join(chunks)
```

Notes:

- The `_iter` inner async generator is the idiomatic pattern for returning an `AsyncIterator` from an `async def` method. It is required because `async def` cannot `yield` and be used with `return` in the same function body.
- Helper logic that does not close over instance state is a `@staticmethod` — never a module-level function.
- The base class provides `_drain_bytes(body)` and `_drain_records(records)` helpers you can use instead of writing your own `_drain_all`.

---

## Step 3 — Handling Optional Dependencies

Every format that requires a third-party library follows the **lazy import pattern**:

```python
async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
    try:
        import widgetlib  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(
            "WidgetFormat requires 'widgetlib'. "
            "Install via `pip install pirn[widget]`."
        ) from exc
    ...
```

Rules:

- The import happens inside the method, not at module top-level.
- The re-raised `ImportError` must include the exact `pip install pirn[<extra>]` command.
- Use `from exc` to preserve the original traceback.
- Add `# type: ignore[import-not-found]` so pyright does not complain when the optional package is absent.
- Formats with **no** optional dependency (CSV, plain text, FASTQ's stdlib path) need no guard.

---

## Step 4 — PHI Safety Conventions (healthcare formats)

Any format that may carry Protected Health Information (HIPAA) must follow these rules:

1. **Never emit raw identifiers.** Hash identifier fields (e.g. `PatientID`) with SHA-256 and emit only the hex digest as `{field}_hash`.
2. **Drop prohibited fields.** Declare a `_phi_keywords: ClassVar[frozenset[str]]` listing all HIPAA-covered field names and scrub them from the emitted `metadata` mapping before returning records.
3. **Document the redaction in the module docstring** under a `PHI safety` heading.
4. **Do not log** any field value that may contain PHI, even at DEBUG level.

Example (abridged from `DicomFormat`):

```python
_phi_keywords: ClassVar[frozenset[str]] = frozenset({
    "PatientName",
    "PatientBirthDate",
    "PatientAddress",
    # add all known synonyms
})

@staticmethod
def _hash_patient_id(raw: str) -> str:
    import hashlib
    return hashlib.sha256(raw.encode()).hexdigest()

@staticmethod
def _sanitise_metadata(dataset: Any) -> dict[str, Any]:
    result = {}
    for key, value in dataset.items():
        if key in MyFormat._phi_keywords:
            continue
        result[key] = value
    return result
```

Healthcare formats (DICOM, HL7 v2, FHIR, CDA) all follow this pattern. If you are adding a new healthcare format, study `dicom_format.py` and `hl7v2_format.py` before implementing.

---

## Step 5 — Tests

### File location

```
tests/unit/domains/connectors/file_formats/test_{name}_format.py
```

Slow tests (any test that calls a real external library and takes > 1 s) get:

```python
import pytest
pytestmark = pytest.mark.slow
```

Integration tests (anything hitting real network or filesystem) go under `tests/integration/`.

### Skipping when the optional dependency is absent

If the format requires an optional extra, add this at the top of the test file (before importing the format class):

```python
pytest.importorskip("widgetlib")
```

This causes the entire test module to be skipped with a clean `SKIP` reason when the library is absent. Do not try to catch `ImportError` inside individual tests.

### Using FormatRoundTrip

Every format must have at least one round-trip test. Import the shared helper:

```python
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)
```

`FormatRoundTrip` provides three static methods:

| Method | What it does |
|--------|-------------|
| `encode(format, records) -> bytes` | Calls `format.write(records)` and concatenates all chunks. |
| `decode(format, payload) -> list[Mapping]` | Calls `format.read(payload)` and collects all records. |
| `assert_round_trip(format, records)` | Encodes then decodes; asserts length equality and per-row equality. |

### Recommended test structure

```python
"""Unit tests for :class:`WidgetFormat`."""

from __future__ import annotations

import pytest

pytest.importorskip("widgetlib")   # skip entire module if not installed

from pirn.domains.connectors.file_formats.widget_format import WidgetFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestWidgetFormatConstruction:
    def test_default_construction(self) -> None:
        fmt = WidgetFormat()
        assert fmt.schema_version == 2

    def test_schema_version_must_be_int(self) -> None:
        with pytest.raises(TypeError):
            WidgetFormat(schema_version="2")  # type: ignore[arg-type]

    def test_schema_version_rejects_bool(self) -> None:
        with pytest.raises(TypeError):
            WidgetFormat(schema_version=True)  # type: ignore[arg-type]

    def test_unsupported_schema_version_rejected(self) -> None:
        with pytest.raises(ValueError):
            WidgetFormat(schema_version=99)


class TestWidgetFormatProperties:
    def test_name(self) -> None:
        assert WidgetFormat().name == "widget"

    def test_streaming_is_false(self) -> None:
        assert WidgetFormat().streaming is False


class TestWidgetFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_basic(self) -> None:
        fmt = WidgetFormat()
        records = [
            {"id": "w1", "value": 42},
            {"id": "w2", "value": 99},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_empty(self) -> None:
        await FormatRoundTrip.assert_round_trip(WidgetFormat(), [])

    @pytest.mark.asyncio
    async def test_round_trip_single_row(self) -> None:
        records = [{"id": "only", "value": 1}]
        await FormatRoundTrip.assert_round_trip(WidgetFormat(), records)
```

Test class naming: `Test{ClassName}Construction`, `Test{ClassName}Properties`, `Test{ClassName}RoundTrip`, `Test{ClassName}Decoding`, `Test{ClassName}Encoding`. These mirror the pattern used across the existing suite.

---

## Step 6 — Register the Format

### Add to `__init__.py`

Open `pirn/domains/connectors/file_formats/__init__.py` and add your class to the `__all__` list and the conditional import block:

```python
# In the appropriate section (e.g. "# Scientific" or "# ML artifacts"):
try:
    from pirn.domains.connectors.file_formats.widget_format import WidgetFormat
except ImportError:  # widgetlib not installed
    pass
```

### Add to `pyproject.toml`

In `[project.optional-dependencies]`, add a new entry in the `# File format extras` section:

```toml
widget = ["widgetlib>=1.0"]
```

If the format belongs to an existing category (e.g. all healthcare formats share `pirn[health]`), add the new dependency to the existing aggregate extra rather than creating a new one.

---

## Step 7 — Run the Full Test Suite

```bash
# Run unit tests (fast path, no slow/integration):
uv run pytest tests/unit/ -x

# Run only your new format tests:
uv run pytest tests/unit/domains/connectors/file_formats/test_widget_format.py -v

# Include slow tests:
uv run pytest tests/unit/ -m slow -x

# Run with coverage (check you hit every branch):
uv run pytest tests/unit/ --cov=pirn/domains/connectors/file_formats/widget_format --cov-report=term-missing
```

The CI gate runs `ruff check`, `pyright`, and `pytest tests/unit/` in that order. All three must pass before a PR is merged.

```bash
# Lint
uv run ruff check pirn/domains/connectors/file_formats/widget_format.py

# Type-check
uv run pyright pirn/domains/connectors/file_formats/widget_format.py
```

---

## Quick Checklist

Before opening a PR, verify:

- [ ] One class, one file; file named `{format_name}_format.py`.
- [ ] No module-level constants — configuration is `ClassVar` or constructor parameters.
- [ ] No bare `except:` — every `except` names a specific exception type.
- [ ] No nested function definitions that could be `@staticmethod`.
- [ ] Optional imports are lazy (inside the method body, not at module top-level).
- [ ] `ImportError` re-raised with exact `pip install pirn[<extra>]` instruction.
- [ ] `_phi_keywords` and sanitisation logic present for any healthcare format.
- [ ] `pytest.importorskip("<lib>")` at the top of the test file for optional-dep formats.
- [ ] `TestConstruction`, `TestProperties`, `TestRoundTrip` classes all present.
- [ ] Round-trip test covers: basic rows, empty input, single row.
- [ ] Format class added to `__init__.py` under a `try/except ImportError`.
- [ ] Optional extra declared in `pyproject.toml` under `# File format extras`.
- [ ] `ruff check` passes.
- [ ] `pyright` passes (no new type errors).
- [ ] `pytest tests/unit/` passes with all existing tests still green.

**See also:** [Connectors — Format Matrix](../connectors/index.md), [Data Domain](../domains/data.md#file-formats)
