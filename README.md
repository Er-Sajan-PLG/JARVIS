# JARVIS

A FastAPI-based research assistant with PDF ingestion, RAG search, and Unlimited-OCR support.

## Start the service

1. Create and activate the Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the FastAPI server from the repository root:

```bash
cd /home/sajan/JARVIS
.venv/bin/python -m app.api.server
```

If you see `ModuleNotFoundError: No module named 'app'`, use:

```bash
cd /home/sajan/JARVIS
PYTHONPATH=. .venv/bin/python -m app.api.server
```

4. Open the web UI in your browser:

```text
http://localhost:8000
```

## Notes

- The knowledge ingestion path uses `knowledge.ocr_engine = "unlimited"` by default.
- If you use remote OCR, set `knowledge.remote_ocr_url` in `config.yaml`.
- No `profiles:` section is needed in `config.yaml`; only `models:` is used for routing.
- Cloud provider API keys should be set in `.env` if you want to use OpenRouter, Grok, or Google.
- For production, use a proper process manager or container runtime instead of the built-in development server.
