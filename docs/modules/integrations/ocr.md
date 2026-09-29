# OCR Integration

**Status**: ACTIVE
**Type**: reference
**Source**: `app/integrations/ocr/`, `app/api/ocr/routes.py`, `app/config/settings.py` (`OCRConfig`), `app/utils/pdf.py` at HEAD
**Last Updated**: 2026-09-30

---

## Overview

Text extraction from an uploaded file. The engine is **Tesseract**, invoked as a
system binary. There is one backend; the previous two are deleted (see
[ADR-018](../../adr/ADR-018-ocr-engine-is-tesseract.md)).

Digital PDFs are read from their embedded text layer and are **not** OCR'd. Only
pages whose text layer is absent or below `native_text_min_chars` are rendered and
sent to the engine. This is the per-page strategy the deleted
`app/knowledge/extract.py` used; it was restored here because OCR-ing a digital PDF
is both wasteful and less accurate than reading the text directly.

**Language support is English-only** (`OCRConfig.language = "eng"`). The code path
accepts Tesseract's `eng+deu` form, but only `eng` and `osd` traineddata are
installed on this host. Any other language needs its `tesseract-ocr-<lang>`
package.

## Architecture

```
OCRService (service.py)
├── ModelManager (model_manager.py)          selects and loads one backend
│   └── TesseractBackend (backends/tesseract_ocr.py)   subprocess → /usr/bin/tesseract
├── app/utils/pdf.py                         extract_pages(): native text, else render
└── schemas.py                               request/response models, single OCRResult
```

| Module | Responsibility |
|---|---|
| `service.py` | Orchestration: route a file to the PDF or image path, enforce the per-page timeout, assemble `OCRResult` |
| `model_manager.py` | One lazily-loaded backend. Registers a backend **only after `load()` succeeds** |
| `app/integrations/ocr/backends/base.py` | `OCRBackend` ABC; re-exports the single `OCRResult` |
| `app/integrations/ocr/backends/tesseract_ocr.py` | Resolves the binary, validates languages, runs one subprocess per image |
| `schemas.py` | `OCRBackend`, `OCRRequest`, `OCRResult`, `HealthResponse`, `BackendInfo`, `ModelManagerStatus`, `OCRHealth` |
| `app/utils/pdf.py` | `extract_pages()` — per-page native-vs-scanned decision; `Page` dataclass |

There is **no `config.py`** in the package. `OCRSettings` there duplicated
`OCRConfig` and was imported by nothing but the two deleted backends.

## Configuration

All settings live in `Settings.ocr` — `OCRConfig` in `app/config/settings.py`.
There is exactly one place to change them.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `engine` | `str` | `"tesseract"` | Selected engine name |
| `binary_path` | `str` | `"tesseract"` | Absolute path or bare name, resolved with `shutil.which` at load |
| `language` | `str` | `"eng"` | Tesseract language code(s); `+`-joined for several |
| `page_timeout_seconds` | `int` | `120` | Per-page subprocess timeout |
| `native_text_min_chars` | `int` | `20` | At or above this many native characters, a PDF page skips OCR |
| `max_upload_size_mb` | `int` | `100` | Upload ceiling; exceeding it is `413` |
| `allowed_extensions` | `list[str]` | `.pdf .png .jpg .jpeg .tiff .tif .bmp .webp` | Leading-dot, lowercased |
| `thread_pool_workers` | `int` | `2` | Executor width for blocking engine calls |

## Endpoints

All three require the API key. The router declares
`dependencies=[Depends(_validate_api_key)]` at `app/api/ocr/routes.py:67`, so the
gate applies to every route on it.

| Method | Path | Success | Failure codes |
|---|---|---|---|
| `GET` | `/api/ocr/health` | `200 HealthResponse` | — (never 500) |
| `POST` | `/api/ocr/process` | `200 OCRResult` | `400` unsupported extension or null byte; `413` oversize; `503` engine unavailable; `502` processing failed |
| `POST` | `/api/ocr/process-path` | `200 OCRResult` | `400`, `404` path missing or not a file, `503`, `502` |

`503` and `502` are distinguished by whether the message names the engine as
unavailable, so an operator can tell "not installed" from "this file failed".

### `GET /api/ocr/health`

```json
{"status": "healthy", "backend": "tesseract", "model_loaded": true,
 "device": "cpu", "error": null, "version": "1.0.0"}
```

`status` is `"healthy"` or `"degraded"`. **`"loading"` no longer exists** — with
tesseract there is no load step, and the old value meant both "never attempted" and
"failed permanently", which made it useless as a signal. `"degraded"` carries the
reason in `error`.

The handler wraps everything in `try/except` and returns `degraded` on any failure.
This endpoint returning a permanent `500` after one bad request was an observed
defect; it is now structurally impossible.

## Behaviour notes

**A failed load is never cached.** `ModelManager` registers a backend in
`_backends` only after `load()` returns successfully; a failure is recorded in
`_load_error` and the manager stays retryable. Previously the backend was
registered first, so one failed `load()` was permanent — and `get_status()` then
called `get_info()` on the broken object and raised, which is what produced the
permanent 500.

**Blocking work leaves the event loop.** `process()` runs in a thread pool via
`asyncio.wait_for(loop.run_in_executor(...), page_timeout_seconds * len(paths))`.
The old code called the engine inline on the event loop while holding a
`threading.Lock`; a stub load of 1.0 s blocked the loop entirely (a ticker task
fired zero times).

**Temp directories always go.** Uploads are written to
`tempfile.TemporaryDirectory(prefix="jarvis_ocr_")` and removed by its context
manager on both the success and the error path. The cleanup does not depend on a
`BackgroundTasks` entry, which Starlette drops when the handler raises.

**Only `Path(filename).name` is used.** The client filename is reduced to a single
path component, and a name containing a NUL byte is rejected with `400` before any
filesystem call (it would otherwise reach `open()` and raise `ValueError`).

**`dpi` is bounded** to `50..600` on `OCRRequest` and on the `process` form field.
It multiplies the pixmap allocation for every rendered page, so unbounded it was a
memory-exhaustion lever.

**`processing_time_seconds` has a default.** The backend cannot know it, so
`OCRResult.processing_time_seconds` defaults to `0.0` and the service sets it. The
service previously returned the backend's *dataclass* here while being annotated for
the pydantic model — two types with the same name, one of which had no such field
at all.

## Verification

```bash
.venv/bin/python -m pytest tests/unit/ -k "ocr or pdf" -q
```

The suite that matters is `tests/unit/test_ocr_end_to_end.py`: it drives the real
router, real service and real engine with no stubs, and asserts on **text extracted
from a generated file**. Every other OCR test replaces something at the seam that
was broken — which is exactly why the subsystem stayed green for two months while
no request could succeed.

A manual round trip:

```bash
.venv/bin/python -c "
import pymupdf
d = pymupdf.open(); p = d.new_page()
p.insert_text((40,110), 'PROOF 12345', fontsize=26)
p.get_pixmap(dpi=200).save('/tmp/proof.png')"
tesseract /tmp/proof.png stdout -l eng
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `health` is `degraded`, error names the binary | Tesseract not installed, or `binary_path` wrong | `sudo apt install tesseract-ocr` |
| `load()` raises naming a language | Missing traineddata for `OCRConfig.language` | `sudo apt install tesseract-ocr-<lang>`, or set `language` to an installed one |
| `400 Unsupported file type` | Extension not in `allowed_extensions` | Add it to `Settings.ocr.allowed_extensions` (leading dot, lowercase) |
| `413` | Over `max_upload_size_mb` | Raise the limit, or split the file |
| Empty `markdown` on a scanned page | Poor scan quality, or `dpi` too low | Raise `dpi` (max 600), or pre-process the scan |
| A digital PDF comes back `0 native, N ocr` | Its text layer is below `native_text_min_chars` | Lower that threshold if the text layer is genuinely usable |

## Related

- [ADR-018: OCR engine is Tesseract](../../adr/ADR-018-ocr-engine-is-tesseract.md) — why, and what was rejected
- `docs/API_CONTRACT.md` §7 — the endpoint contract
- ADR-010 — Adapters & Integrations Isolation
