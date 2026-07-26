Local Remote OCR example

This folder contains a minimal FastAPI-based OCR service example that JARVIS can call via `RemoteOCREngine`.

API contract

- POST /ocr/process
  - multipart/form-data field `file` containing the image (PNG/JPEG)
  - returns JSON: { "text": "recognized text" }
- GET /health
  - returns 200 OK and JSON { "status": "ok" }

Run (dev):

Install dependencies (optional; you can skip if you only want the example):

```bash
pip install fastapi uvicorn pillow pytesseract
```

Start service:

```bash
uvicorn external.remote_ocr_example.service:app --reload --port 9000
```

Notes

- The example tries to use `pytesseract` + `Pillow` if installed; otherwise it returns a helpful error message prompting to install Tesseract or use another backend.
- This is intentionally simple so you can swap in any OCR implementation behind `/ocr/process`.
