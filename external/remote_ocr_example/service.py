"""Minimal external OCR service example for JARVIS.

Provides:
- POST /ocr/process -> multipart `file` -> JSON {"text": "..."}
- GET /health -> JSON {"status": "ok"}

The implementation uses `pytesseract` + `Pillow` if available; otherwise
it returns an explanatory error (so the service is still useful as a stub).
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import io

app = FastAPI(title="Remote OCR Example")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ocr/process")
async def process(file: UploadFile = File(...)):
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty file")

    # Try to run pytesseract if available
    try:
        from PIL import Image
        import pytesseract
    except Exception as e:
        return JSONResponse(status_code=501, content={
            "error": "pytesseract or Pillow not available. Install with: pip install pillow pytesseract; also ensure Tesseract OCR binary is installed on the host.",
            "details": str(e),
        })

    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        raise HTTPException(400, f"could not open image: {e}")

    try:
        text = pytesseract.image_to_string(img)
    except Exception as e:
        raise HTTPException(500, f"OCR failed: {e}")

    return {"text": text}
