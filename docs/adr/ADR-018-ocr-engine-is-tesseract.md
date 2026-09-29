# ADR-018: OCR engine is Tesseract, and the two dead backends are removed

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-09-30

> Drift trap for this type: Being *edited* to look correct in hindsight. An ADR that is rewritten to match current reality destroys the only record of why the decision was made.

---

## Context

The OCR subsystem served **no successful request, ever**. A forensic pass at
`e643618` established this with a live `TestClient` against the real router:

| Request (valid key) | Observed |
|---|---|
| `GET /api/ocr/health` (cold) | `200 {"status":"loading","backend":null}` |
| `POST /api/ocr/process` (PNG) | `500 "Processing failed: paddleocr not installed"` |
| `POST /api/ocr/process-path` (PNG) | `500` |
| `GET /api/ocr/health` (afterwards) | **`500` permanently** |

Both backends read `self.settings.ocr.*` across **22 call sites**, but
`Settings` (`app/config/settings.py`) had **no `ocr` field and never had one**
(`hasattr(get_settings(), 'ocr')` → `False`; `git log --all -S OCRConfig`
returns empty). Every `load()` raised `AttributeError` before it could import an
engine or read a weight. The first appearance of `self.settings.ocr` is
`81e45f0` (2026-07-26), so the backends were dead from the day they were written.

Neither engine could have run on the target host even with that fixed:

- **Unlimited-OCR** — `unlimited_device` defaulted to `"cuda"` while
  `torch.cuda.is_available()` is `False`; it needs multi-GB weights (not cached;
  `~/.cache/huggingface/hub` holds only docling and faster-whisper),
  `accelerate` is not installed, and it loads with `trust_remote_code=True`,
  which executes Hub-supplied Python.
- **PaddleOCR** — not installed, although `requirements.txt:162` pins
  `paddleocr==3.7.0`; and the code was written against the **2.x** API
  (`self.ocr_engine.ocr(img_path, cls=True)` at `paddle_ocr.py:82`, `use_gpu`,
  `show_log`), while 3.7.0's `PaddleOCR.predict` is keyword-only with no
  `**kwargs` → `TypeError`. Installing the pinned version would not have fixed it.

The 246-test OCR suite stayed green throughout, because its fixtures replaced
the system at the exact seam that was broken: `test_ocr_backends.py` **created
the missing attribute itself** (`settings.ocr = OCRSettings(...)`) before
asserting `get_info()` worked.

The feature has one intended purpose: **extract text from a file uploaded in the
web UI**. It is English-only for now.

## Decision

**OCR uses the `tesseract` system binary, through a single `TesseractBackend`.**
`PaddleOCRBackend` and `UnlimitedOCRBackend` are deleted, along with the
duplicate pydantic `OCRSettings` shim that lived in the package's own `config.py`.
Configuration lives in exactly one place: `Settings.ocr` (`OCRConfig` in
`app/config/settings.py`).

PDFs use a two-path, **per-page** strategy: the embedded text layer via PyMuPDF
where it exists, and OCR of a rendered page only where it does not.

## Alternatives considered

**1. Fix the settings attribute and keep both engines.** Rejected: it repairs one
line and leaves two engines that still cannot run here — one needing absent CUDA
hardware, the other a package whose pinned version is API-incompatible with the
code that calls it. It also keeps engine choice as a runtime branch
(`torch.cuda.is_available()`), which is what made the failure mode
hardware-dependent and untestable on this machine.

**2. Install PaddleOCR and port the backend to the 3.x API.** Rejected as the
first move, not permanently: it is a real option, but it costs a large dependency
plus an API port and buys nothing tesseract does not already do for English
document text. It stays open if table-structure recognition is ever needed — that
was PP-StructureV3's purpose, and it is the one capability genuinely lost.

**3. Cloud OCR.** Rejected on the privacy invariant: sensitive documents must
never leave the machine. It would also add per-page cost against a hard budget
and a network dependency in the upload path.

**4. Use the already-cached docling models.** Rejected for now: 506 MB of
`docling-models` and `docling-layout-heron` are on disk, but the `docling`
package itself is not installed, and docling is a document-structure tool — a
heavier answer than plain text extraction needs.

**5. Delete the OCR surface entirely.** Seriously considered: OCR had no in-app
consumer (`get_ocr_service` was referenced only by its own three routes; the RAG
consumer was deleted in `41f93b9`), the docs described an API that never existed,
and the frontend polled two endpoints that do not exist. Rejected because the
owner confirmed the intent — upload a file, get its text — so the surface is
wanted and only its implementation was wrong.

## Consequences

**Easier.** No weights to download, no GPU, no `trust_remote_code`, no model
lifecycle. Three defect classes disappear *structurally* rather than by patching,
because there is nothing to load: no multi-minute load blocking the event loop
under a lock; no "failed load registered forever" state poisoning `/health`; and
no unreachable "selected but not loaded" state to report dishonestly. `torch` is
no longer imported by `model_manager.py`, removing ~774 MB RSS and ~0.9 s from
`app.main`'s import path.

**Harder.** Table and formula structure recognition is gone with PP-StructureV3.
Non-English scripts need a `tesseract-ocr-<lang>` package installed and
`OCRConfig.language` changed — the code path supports it (`eng+deu` form), but
only `eng` and `osd` are installed today.

**Now hard to undo.** `OCRBackend` values `unlimited` and `paddle` are removed, a
client-visible breaking change: a caller passing either now gets a 422 rather
than a 500 from a backend that cannot start. Restoring an engine means adding a
backend class and a config section, not flipping a flag.

**Verified.** An end-to-end run through the real router, real service and real
engine extracts `"END TO END PROOF 24680"` from a generated PNG in 0.19 s, and
`"NATIVE PDF TEXT LAYER"` from a digital PDF with **zero** OCR
(`model_info: "1 native, 0 ocr"`). `/api/ocr/health` reports
`{"status":"healthy","backend":"tesseract","device":"cpu"}` and survives a failed
request.

**Assumed, not verified.** Whether `tesseract` produces *correct* text on real
scanned documents (the fixture is machine-generated text); accuracy on poor
scans, handwriting or rotated pages; and behaviour on a PDF whose pages are
images behind a misleading text layer.

## Related

- `docs/modules/integrations/ocr.md` — the reference for the subsystem as it is now
- `docs/API_CONTRACT.md` — the endpoint contract (auth is required on all three routes)
- ADR-010 — Adapters & Integrations Isolation
- `app/config/settings.py` (`OCRConfig`), `app/integrations/ocr/backends/tesseract_ocr.py`
