"""WebSocket voice handler."""
import asyncio
import logging
import tempfile
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.integrations.voice import VoiceConfig, VoiceService

logger = logging.getLogger(__name__)

voice_ws_router = APIRouter(tags=["Voice"])


@voice_ws_router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """WebSocket endpoint for voice interaction."""
    await websocket.accept()
    
    config = VoiceConfig.from_env()
    service = VoiceService(config)
    
    try:
        await websocket.send_json({
            "type": "status",
            "message": "Voice session active. Send audio chunks."
        })
        
        while True:
            # Receive audio data
            data = await websocket.receive_bytes()
            
            # Transcribe
            text = service.listen_bytes(data)
            
            if not text:
                await websocket.send_json({
                    "type": "error",
                    "message": "Could not transcribe audio"
                })
                continue
            
            # Check for wake word
            if not service.is_wake_word(text):
                await websocket.send_json({
                    "type": "transcription",
                    "text": text,
                    "wake_word_detected": False
                })
                continue
            
            # Process command (remove wake word)
            command = text.lower().replace(config.wake_word, "").strip()
            
            await websocket.send_json({
                "type": "transcription",
                "text": text,
                "wake_word_detected": True,
                "command": command
            })
            
            # TODO: Process command through brain
            response = f"Processing: {command}"
            
            # Synthesize response
            audio_path = service.speak(response)
            
            await websocket.send_json({
                "type": "response",
                "text": response,
                "audio_path": audio_path
            })
    
    except WebSocketDisconnect:
        logger.info("Voice WebSocket disconnected")
    except Exception as e:
        logger.error("Voice WebSocket error: %s", e)
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
