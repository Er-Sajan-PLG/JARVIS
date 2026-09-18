"""Voice REST API: speech-to-text and text-to-speech for the phone clients.

STT runs locally via faster-whisper (tiny model on CPU by default; set
``JARVIS_STT_MODEL`` to ``base``/``small`` for accuracy). TTS uses Edge TTS
(no API key, natural voices; set ``JARVIS_TTS_VOICE`` to change voice).

The PWA/APK records with MediaRecorder and POSTs audio here; the reply text
from ``/api/chat`` is POSTed back for spoken playback. Nothing streams —
request/response keeps the phone client simple and the server stateless.
"""

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.adapters.http.router import validate_api_key

logger = logging.getLogger(__name__)

voice_router = APIRouter(
    prefix="/api/v1/voice",
    tags=["Voice"],
    dependencies=[Depends(validate_api_key)],
)

_stt_model = None


def _get_stt_model():
    """Lazy-load faster-whisper once; model downloads on first use (~75MB)."""
    global _stt_model
    if _stt_model is None:
        import os

        from faster_whisper import WhisperModel

        name = os.getenv("JARVIS_STT_MODEL", "tiny")
        _stt_model = WhisperModel(name, device="cpu", compute_type="int8")
        logger.info("Loaded faster-whisper model: %s", name)
    return _stt_model


class TTSRequest(BaseModel):
    text: str
    voice: str | None = None


@voice_router.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)) -> dict[str, Any]:
    """Transcribe uploaded audio (webm/ogg/wav from MediaRecorder) to text."""
    raw = await audio.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty audio")
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="audio too large (10MB max)")

    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    try:
        model = _get_stt_model()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(raw)
            tmp.flush()
            segments, _info = model.transcribe(tmp.name)
            text = " ".join(s.text for s in segments).strip()
    except Exception as exc:  # noqa: BLE001
        logger.error("STT error: %s", exc)
        raise HTTPException(status_code=500, detail="transcription failed") from exc
    return {"success": True, "text": text}


@voice_router.post("/tts")
async def text_to_speech(payload: TTSRequest) -> Response:
    """Synthesize text to MP3 audio bytes."""
    import os

    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    voice = payload.voice or os.getenv("JARVIS_TTS_VOICE", "en-US-ChristopherNeural")
    try:
        import edge_tts

        communicate = edge_tts.Communicate(text[:2000], voice)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        audio = b"".join(chunks)
        if not audio:
            raise RuntimeError("empty synthesis")
    except Exception as exc:  # noqa: BLE001
        logger.error("TTS error: %s", exc)
        raise HTTPException(status_code=500, detail="synthesis failed") from exc
    return Response(content=audio, media_type="audio/mpeg")


@voice_router.get("/status")
async def voice_status() -> dict[str, Any]:
    """Voice service status (no model load)."""
    import os

    return {
        "stt_model": os.getenv("JARVIS_STT_MODEL", "tiny"),
        "stt_loaded": _stt_model is not None,
        "tts_voice": os.getenv("JARVIS_TTS_VOICE", "en-US-ChristopherNeural"),
    }
