# Third-Party Integrations Subsystem (`app/integrations/`) - Version-by-Version History

## Version-by-Version Evolutionary History

### Version v0.1.0 (`e13ee67`)
- **Direct HTTP Requests**: Direct `httpx` / `urllib` calls to Ollama local API inside model client module.

### Version v2.2.0 (`b2c2211`)
- **ChromaDB Client**: Direct instantiation of `chromadb.PersistentClient` in `VectorRetriever`.

### Version v3.0.0 (`81e45f0`)
- **OCR Subsystem**: Introduced PaddleOCR, PyMuPDF (`fitz`), and UnlimitedOCR services in `app/services/ocr/`.

### Version v3.0.0 Refactored (`ec0dc4e`) - Current HEAD
- **Third-Party Integrations Package (`app/integrations/`)**:
  - `app/integrations/ocr/`: OCR service backends (`PaddleOCRBackend`, `UnlimitedOCRBackend`, `OCRService`).
  - `app/integrations/vector/chroma.py`: `ChromaVectorStore` wrapper isolating ChromaDB client and `OllamaEmbeddingFunction`.
- **Active Invariants at HEAD**:
  1. Isolates 3rd-party open-source libraries and vendor SDKs behind clean JARVIS interfaces.
  2. Prevents vendor API leaks into core domain business logic.
