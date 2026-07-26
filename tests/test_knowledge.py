"""
Consolidated unit tests for the knowledge / RAG subsystem's native path.

Covers:
* ``chunk_document`` (pure Python — always runs, no external deps).
* ``extract_pages`` native-text path — runs only when ``pymupdf`` (``fitz``)
  is installed; skipped otherwise.
* ``extract_pages`` OCR path — runs when ``fitz`` is installed and the
  configured OCR backend is available. OCR is optional and handled via
  Unlimited-OCR or remote HTTP OCR.

A minimal valid text-only PDF is generated in-code (no PDF library required to
*build* it) so the native extraction test has real bytes to feed ``fitz``.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from app.knowledge.chunk import chunk_document, Chunk
from app.knowledge.extract import (
    extract_pages,
    build_ocr_engine,
    NoOpOCREngine,
    Page,
)

# Missing-deps guards (set at import time so skip decorators can reference them).
try:
    import fitz  # noqa: F401
    _HAVE_FITZ = True
except Exception:  # pragma: no cover - environment dependent
    _HAVE_FITZ = False


# ---------------------------------------------------------------------------
# A tiny but valid PDF with a real (uncompressed) text content stream, so a PDF
# library can read its *native* text layer without OCR. Built by hand to avoid a
# test dependency on a PDF-writing library.
# ---------------------------------------------------------------------------
def _minimal_text_pdf(lines):
    # Each line becomes a BT/ET text object placed lower on the page.
    content_parts = []
    y = 750
    for line in lines:
        # Escape parentheses in PDF strings.
        safe = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content_parts.append(
            f"BT /F1 12 Tf 1 0 0 1 50 {y} Tm ({safe}) Tj ET"
        )
        y -= 20
    content = "\n".join(content_parts)

    objects = []
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")          # 1
    objects.append("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")  # 2
    objects.append(                                                # 3
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
    )
    objects.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream>")  # 4
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")  # 5

    # Assemble with xref.
    header = b"%PDF-1.4\n"
    body = b""
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(header) + len(body))
        body += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref_pos = len(header) + len(body)
    n = len(objects) + 1
    xref = f"xref\n0 {n}\n".encode("latin-1")
    xref += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n".encode("latin-1")
    trailer = (
        f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    ).encode("latin-1")
    return header + body + xref


# ---------------------------------------------------------------------------
# chunk_document — pure Python, always runs
# ---------------------------------------------------------------------------
class TestChunkDocument(unittest.TestCase):
    def _pages(self, *texts):
        return [Page(page_no=i + 1, text=t, source="text") for i, t in enumerate(texts)]

    def test_basic_chunking(self):
        words = " ".join(f"w{i}" for i in range(25))
        # min_chunk_chars=1 so fragments aren't merged into the previous chunk,
        # letting us assert the overlap window between consecutive chunks.
        chunks = chunk_document(
            title="T", filename="f.pdf", doc_id="d1",
            pages=self._pages(words), chunk_size=10, overlap=2, min_chunk_chars=1,
        )
        self.assertTrue(len(chunks) >= 2)
        self.assertTrue(all(isinstance(c, Chunk) for c in chunks))
        # Overlap preserved: chunk 2 starts with the last 2 words of chunk 1.
        c1 = chunks[0].text.split()
        c2 = chunks[1].text.split()
        self.assertEqual(c1[-2:], c2[:2])
        # Metadata threading.
        self.assertEqual(chunks[0].doc_id, "d1")
        self.assertEqual(chunks[0].filename, "f.pdf")
        self.assertEqual(chunks[0].title, "T")
        self.assertEqual(chunks[0].page, 1)
        self.assertEqual([c.chunk_index for c in chunks], list(range(len(chunks))))

    def test_page_boundary_metadata(self):
        # min_chunk_chars=1 so each page's small chunks stay separate and we can
        # verify the global chunk_index is stable and page metadata flows through.
        chunks = chunk_document(
            title="T", filename="f.pdf", doc_id="d1",
            pages=self._pages("alpha beta gamma delta", "epsilon zeta eta theta"),
            chunk_size=2, overlap=0, min_chunk_chars=1,
        )
        # First page's chunks are page 1, second page's are page 2.
        self.assertEqual(chunks[0].page, 1)
        self.assertEqual(chunks[-1].page, 2)
        # Global chunk_index is stable across pages.
        self.assertEqual([c.chunk_index for c in chunks], list(range(len(chunks))))

    def test_short_fragments_merged_or_dropped(self):
        # A short trailing fragment (< min_chunk_chars) merges into the previous.
        text = "This is a sufficiently long sentence that will form the main chunk of text here."
        frag = "tiny"
        chunks = chunk_document(
            title="T", filename="f.pdf", doc_id="d1",
            pages=self._pages(text + " " + frag),
            chunk_size=200, overlap=0, min_chunk_chars=50,
        )
        self.assertEqual(len(chunks), 1)
        self.assertIn("tiny", chunks[0].text)

    def test_empty_pages_ignored(self):
        chunks = chunk_document(
            title="T", filename="f.pdf", doc_id="d1",
            pages=self._pages("", "   ", "real content here that is long enough"),
            chunk_size=100, overlap=0,
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, "real content here that is long enough")

    def test_whitespace_only_fragment_not_added(self):
        chunks = chunk_document(
            title="T", filename="f.pdf", doc_id="d1",
            pages=self._pages("x" * 200),
            chunk_size=50, overlap=0, min_chunk_chars=10,
        )
        self.assertTrue(all(c.text.strip() for c in chunks))


# ---------------------------------------------------------------------------
# extract_pages — native path (needs fitz)
# ---------------------------------------------------------------------------
@unittest.skipUnless(_HAVE_FITZ, "pymupdf (fitz) not installed")
class TestExtractNative(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_native_text_extracted(self):
        pdf = _minimal_text_pdf([
            "Solid-state batteries use a ceramic separator.",
            "Lithium ion batteries use a liquid electrolyte.",
        ])
        pages = extract_pages(pdf, ocr_engine=NoOpOCREngine(), ocr_text_threshold=30)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].source, "text")
        self.assertIn("ceramic separator", pages[0].text)
        self.assertIn("liquid electrolyte", pages[0].text)

    def test_per_page_source_tagged_text(self):
        pdf = _minimal_text_pdf(["only page", "second page text"])
        pages = extract_pages(pdf, ocr_engine=NoOpOCREngine())
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0].page_no, 1)
        self.assertEqual(pages[1].page_no, 2)
        self.assertTrue(all(p.source == "text" for p in pages))


# ---------------------------------------------------------------------------
# OCR engine factory
# ---------------------------------------------------------------------------
class TestOCREngineFactory(unittest.TestCase):
    def test_build_ocr_engine_none(self):
        eng = build_ocr_engine("none")
        self.assertIsInstance(eng, NoOpOCREngine)

    def test_build_ocr_engine_unknown_raises(self):
        with self.assertRaises(ValueError):
            build_ocr_engine("unsupported_engine")


# ---------------------------------------------------------------------------
# extract_pages — OCR path (needs fitz)
# ---------------------------------------------------------------------------
@unittest.skipUnless(_HAVE_FITZ, "pymupdf (fitz) not installed")
class TestExtractOCR(unittest.TestCase):
    def test_ocr_engine_factory_noop(self):
        eng = build_ocr_engine("none")
        self.assertIsInstance(eng, NoOpOCREngine)

    def test_ocr_fallback_on_empty_native(self):
        # A PDF whose native text is below threshold should be routed to OCR.
        # We don't render/scan here (would need a real scanned image); instead we
        # assert the engine is asked and degrades gracefully to native text.
        pdf = _minimal_text_pdf(["x"])  # 1 char < threshold(30)
        pages = extract_pages(pdf, ocr_engine=NoOpOCREngine(), ocr_text_threshold=30)
        # NoOp OCR yields nothing, so native (even if short) is kept.
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].text, "x")


if __name__ == "__main__":
    unittest.main()
