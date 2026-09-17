"""Voice integration: STT, TTS, wake word detection."""
import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class VoiceConfig:
    """Voice configuration."""
    stt_model: str = "base"
    tts_provider: str = "pyttsx3"
    elevenlabs_api_key: str = ""
    wake_word: str = "jarvis"
    sample_rate: int = 16000

    @classmethod
    def from_env(cls) -> "VoiceConfig":
        import os
        return cls(
            stt_model=os.getenv("JARVIS_STT_MODEL", "base"),
            tts_provider=os.getenv("JARVIS_TTS_PROVIDER", "pyttsx3"),
            elevenlabs_api_key=os.getenv("JARVIS_ELEVENLABS_API_KEY", ""),
            wake_word=os.getenv("JARVIS_WAKE_WORD", "jarvis"),
            sample_rate=int(os.getenv("JARVIS_SAMPLE_RATE", "16000")),
        )


class SpeechToText:
    """Whisper-based speech-to-text."""
    
    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self._model = None
    
    def _load_model(self):
        """Lazy-load the Whisper model."""
        if self._model is None:
            import whisper
            self._model = whisper.load_model(self.model_name)
        return self._model
    
    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio to text."""
        try:
            model = self._load_model()
            result = model.transcribe(audio_path)
            return result["text"].strip()
        except Exception as e:
            logger.error("STT transcription error: %s", e)
            return ""
    
    def transcribe_bytes(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes to text."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
            f.write(audio_bytes)
            f.flush()
            return self.transcribe(f.name)


class TextToSpeech:
    """TTS with ElevenLabs primary, pyttsx3 fallback."""
    
    def __init__(self, config: VoiceConfig | None = None):
        self.config = config or VoiceConfig.from_env()
    
    def synthesize(self, text: str, output_path: str | None = None) -> str | None:
        """Synthesize text to speech."""
        if self.config.tts_provider == "elevenlabs" and self.config.elevenlabs_api_key:
            return self._synthesize_elevenlabs(text, output_path)
        return self._synthesize_local(text, output_path)
    
    def _synthesize_elevenlabs(self, text: str, output_path: str | None = None) -> str | None:
        """Synthesize using ElevenLabs API."""
        try:
            import requests
            
            url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.config.elevenlabs_api_key,
            }
            data = {
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
            }
            
            response = requests.post(url, json=data, headers=headers)
            if response.status_code != 200:
                logger.error("ElevenLabs TTS error: %s", response.status_code)
                return None
            
            if output_path is None:
                import tempfile
                output_path = tempfile.mktemp(suffix=".mp3")
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            return output_path
        except Exception as e:
            logger.error("ElevenLabs TTS error: %s", e)
            return None
    
    def _synthesize_local(self, text: str, output_path: str | None = None) -> str | None:
        """Synthesize using local pyttsx3."""
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            
            if output_path is None:
                import tempfile
                output_path = tempfile.mktemp(suffix=".wav")
            
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            return output_path
        except Exception as e:
            logger.error("Local TTS error: %s", e)
            return None


class WakeWordDetector:
    """Simple wake word detection (Porcupine or fallback)."""
    
    def __init__(self, wake_word: str = "jarvis"):
        self.wake_word = wake_word.lower()
        self._detector = None
    
    def detect(self, text: str) -> bool:
        """Detect wake word in text."""
        return self.wake_word in text.lower()
    
    def detect_audio(self, audio_path: str) -> bool:
        """Detect wake word in audio (transcribe then check)."""
        stt = SpeechToText()
        transcription = stt.transcribe(audio_path)
        return self.detect(transcription)


class VoiceService:
    """High-level voice service combining STT, TTS, and wake word."""
    
    def __init__(self, config: VoiceConfig | None = None):
        self.config = config or VoiceConfig.from_env()
        self.stt = SpeechToText(self.config.stt_model)
        self.tts = TextToSpeech(self.config)
        self.wake_word = WakeWordDetector(self.config.wake_word)
    
    def speak(self, text: str) -> str | None:
        """Convert text to speech."""
        return self.tts.synthesize(text)
    
    def listen(self, audio_path: str) -> str:
        """Convert speech to text."""
        return self.stt.transcribe(audio_path)
    
    def listen_bytes(self, audio_bytes: bytes) -> str:
        """Convert speech bytes to text."""
        return self.stt.transcribe_bytes(audio_bytes)
    
    def is_wake_word(self, text: str) -> bool:
        """Check if text contains wake word."""
        return self.wake_word.detect(text)
