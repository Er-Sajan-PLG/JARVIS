# OCR Integration

**Status**: ACTIVE
**Type**: reference
**Source**: `app/integrations/ocr/` at HEAD
**Last Updated**: 2026-09-17

---

## Overview

Optical Character Recognition (OCR) integration supporting multiple backends (PaddleOCR, Unlimited-OCR) with a unified service interface.

## Architecture

```
service.py (OCRService)
├── backends/
│   ├── paddle_ocr.py (PaddleOCR backend)
│   ├── unlimited_ocr.py (Unlimited-OCR backend)
│   └── base.py (Abstract base)
├── config.py (OCR configuration)
├── model_manager.py (Model download/management)
└── schemas.py (Pydantic models)
```

## Configuration

- `JARVIS_OCR_BACKEND`: Backend to use (`paddle` or `unlimited`)
- `JARVIS_OCR_LANG`: Language code (default: `en`)
- `JARVIS_OCR_USE_GPU`: Enable GPU acceleration (default: `false`)

## API

```python
from app.integrations.ocr import OCRService

service = OCRService(backend="paddle")
result = await service.extract_text("path/to/image.png")
# result.text, result.confidence, result.blocks
```

## Backends

| Backend | Speed | Accuracy | GPU | Offline |
|---------|-------|----------|-----|---------|
| PaddleOCR | Fast | High | Yes | Yes |
| Unlimited-OCR | Medium | Very High | No | Yes |
