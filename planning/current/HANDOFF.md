# Session handoff — pirn `feat/domain-knot-libraries`

Compact status for a fresh session / model picking up this branch.

## TL;DR

- Branch `feat/domain-knot-libraries` has **15 commits** ahead of main on PR [#13](https://github.com/snoodleboot-io/pirn/pull/13) (draft).
- Suite: **3261 passing, 6 skipped, 0 failing**.
- Phase 4 (file formats) is **65% done** — 64 of ~98 planned formats shipped across 10 waves.
- One untracked source file (`dicom_format.py`) is partial work from a Round 3 agent that hit a rate limit.
- Two cleanup items + Block 9 docs still pending.

## Where the work lives

| Doc | Purpose |
|-----|---------|
| `planning/current/phase4-progress.md` | **Phase 4 checklist — start here for status** |
| `planning/current/phase4-data-formats-prd.md` | Phase 4 design + wave plan + per-format spec |
| `planning/current/phase3-review-2026-05-01.md` | Phase 3 review findings (most addressed) |
| `planning/current/security-review-2026-05-01.md` | Security review (resolved per-finding) |
| `planning/current/execution-plan.md` | Original Phase 1-3 execution plan |

## Branch state — 15 commits

```
4b2bdbd Phase 4 Round 2 — 38 formats / 456 tests
86436b2 Phase 4 Round 1 — 19 formats / 226 tests
ae90db3 Phase 3 review fixes + Phase 4 foundation
d65ad36 Phase 3 review Wave 1 conventions cleanup
fbd44ed Health source gaps (trials + pathology)
88a92b7 Test coverage for h/s/og (~811 tests)
cb61b6c Phase 3 wave 1 — Block 4/5/6/7/8 source
9413606 Security hardening (B1-1 / B4-1 / B6-1)
fe2978c Security review + LOW fixes
4a7a87b Batch 3.5 — bulk capability migration
542c2d3 Batch 3 — capability interfaces + exemplars
75ff004 Batch 2 cleanup
2622730 Batch 1 cleanup
1c64d10 Extended-tier connectors + PySpark
f786e00 (main…) Phase 2 stabilization
```

## What's done

- All of Phase 2 (data domain tiered architecture).
- All of Phase 3 (agents, ml, health, signal, oilgas + ~272 source files + ~1500 tests).
- Phase 3 review (conventions / standards / security / perf — 24 BLOCKING fixed, security MEDIUM/LOW resolved, perf HIGH applied).
- Phase 4 foundation (FileFormat refinement, CompressedFileFormat, FileSource/Sink, LakehouseTable, FormatRoundTrip helper).
- Phase 4 Rounds 1+2 — 64 file formats including all universal tabular, scientific tabular, lakehouse, codecs, documents, genomics, geospatial, ML artifacts, images.

## What's NOT done — in priority order

### 1. Round 3 (33 formats + 1 partial)

All blocked by rate limits in this session. See `phase4-progress.md` for the full per-format checklist. Five waves remaining:

- **B2 healthcare clinical** (6): FHIR JSON, FHIR XML, HL7v2, CDA XML, define-XML, SDTM XPT
- **B3 healthcare imaging** (5): NIfTI, BIDS, OpenSlide, mzML — and the partial **DICOM** (see below)
- **B5 healthcare biosignal** (4): EDF, EDF+, BDF, BrainVision
- **C1 audio** (6): WAV, FLAC, MP3, OGG, AAC, M4A
- **C2 oil & gas** (7): SEG-Y, LAS, DLIS, WITSML, PRODML, RESQML, SEGD
- **E specialty** (5): ROOT, FITS, GRIB, NetCDF-4, ASDF

Plus the **archive_file_format.py** read/write impls (tar/zip; currently NotImplementedError).

### 2. DICOM — partial work, decision needed

`pirn/domains/connectors/file_formats/dicom_format.py` exists (287 lines, untracked). No test file. Source includes PHI-hash safety per spec. Two paths:

- **(a)** Read it, judge quality, commit as-is + add a test in this session.
- **(b)** Revert it (`rm pirn/domains/connectors/file_formats/dicom_format.py`) and let Wave B3 rebuild it cleanly.

### 3. Cleanup items

- **B4a free helpers**: `fasta_format.py`, `fastq_format.py`, `vcf_format.py`, `bcf_format.py` have parse/serialise helpers at module scope. python.md says "methods belong to classes; no free helpers." Wrap into `@staticmethod` on the relevant class.
- **Verify epub/hdf5 tests**: B4a agent flagged "pre-existing failures" while running concurrently. Suite is currently green so likely flakes, but worth a clean re-run.

### 4. Block 9 — Documentation & polish

Last on the list. Per-domain docs, connector matrix, contributing guide, README, CHANGELOG, mkdocs nav. Held all session for the surface to stop moving.

## How to resume safely

```bash
cd /home/john_aven/Documents/software/pirn
git fetch origin
git checkout feat/domain-knot-libraries
git pull
uv run pytest tests/unit/ --no-header -q
# expect: 3261 passing, 6 skipped, 0 failing
```

If the suite count differs, something has drifted. Stop and reconcile before adding more code.

For Round 3 dispatch, the agent prompts I used are in the chat history of this session. The PRD `phase4-data-formats-prd.md` has the per-format design — anyone with that PRD plus `_format_round_trip.py` can re-issue equivalent prompts. **Each wave's prompt should target ≤7 formats** to fit within agent token quota.

## Things that bit me

- **Parallel agents writing to the same shared file** (e.g., `pyproject.toml`) caused races in earlier rounds — usually self-resolves but watch for conflicts in the extras block.
- **Agents writing module-level free helpers** instead of class staticmethods. Convention check after every wave.
- **`examples/pirn.db` and root `pirn.db`** keep showing up modified after test runs. They're now in `.gitignore` (since `d65ad36`). If they appear, just `git checkout HEAD -- examples/pirn.db`.
- **VS Code crashing kills in-flight agents.** The work that survived in this session was disk-resident at the time; agent context was lost. Health/signal/oilgas tests had to be regenerated post-crash.
- **DEFAULT `SQLiteHistory(path="pirn.db")`** drops a SQLite file in cwd. Pre-existing behaviour. If you instantiate it without a path, expect this.

## Pyproject.toml extras shipped this session

Long list — see commit `4b2bdbd` for the full set. Key ones: parquet, avro, orc, feather, xlsx, ods, hdf5, zarr, matlab, netcdf, zstd, snappy, lz4, delta, iceberg, hudi, pdf, docx, pptx, html, markdown, epub, rtf, genomics, shapefile, geojson, kml, geotiff, geopackage, onnx, safetensors, joblib, pytorch, tensorflow, gguf, tflite, image, tiff, heic.

When adding new format extras, append to the "File format extras" block after the connector extras. Each format with non-trivial deps gets its own extra so the core install stays small.
