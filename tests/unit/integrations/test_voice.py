"""Unit tests for voice integration."""
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.integrations.voice import (
    SpeechToText,
    TextToSpeech,
    VoiceConfig,
    VoiceService,
    WakeWordDetector,
)


@pytest.fixture
def config():
    return VoiceConfig(
        stt_model="base",
        tts_provider="pyttsx3",
        elevenlabs_api_key="test_key",
        wake_word="jarvis",
    )


class TestVoiceConfig:
    def test_default_config(self):
        config = VoiceConfig()
        assert config.stt_model == "base"
        assert config.tts_provider == "pyttsx3"
        assert config.wake_word == "jarvis"

    def test_config_from_env(self):
        with patch.dict(os.environ, {
            "JARVIS_STT_MODEL": "small",
            "JARVIS_TTS_PROVIDER": "elevenlabs",
            "JARVIS_WAKE_WORD": "computer",
        }):
            config = VoiceConfig.from_env()
            assert config.stt_model == "small"
            assert config.tts_provider == "elevenlabs"
            assert config.wake_word == "computer"


class TestSpeechToText:
    def test_transcribe(self):
        stt = SpeechToText("base")
        mock_module = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "Hello world"}
        mock_module.load_model.return_value = mock_model
        
        with patch.dict(sys.modules, {"whisper": mock_module}):
            result = stt.transcribe("test.wav")
            assert result == "Hello world"

    def test_transcribe_error(self):
        stt = SpeechToText("base")
        mock_module = MagicMock()
        mock_module.load_model.side_effect = Exception("Model error")
        
        with patch.dict(sys.modules, {"whisper": mock_module}):
            result = stt.transcribe("test.wav")
            assert result == ""


class TestTextToSpeech:
    def test_synthesize_local(self, config):
        tts = TextToSpeech(config)
        mock_module = MagicMock()
        mock_engine = MagicMock()
        mock_module.init.return_value = mock_engine
        
        with patch.dict(sys.modules, {"pyttsx3": mock_module}):
            result = tts._synthesize_local("Hello", "/tmp/test.wav")
            assert result == "/tmp/test.wav"
            mock_engine.save_to_file.assert_called_once()

    def test_synthesize_elevenlabs(self, config):
        tts = TextToSpeech(config)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"audio_data"
        
        with patch("requests.post", return_value=mock_response):
            with patch("builtins.open", MagicMock()):
                result = tts._synthesize_elevenlabs("Hello", "/tmp/test.mp3")
                assert result == "/tmp/test.mp3"


class TestWakeWordDetector:
    def test_detect_wake_word(self):
        detector = WakeWordDetector("jarvis")
        assert detector.detect("jarvis, what's the weather?") is True
        assert detector.detect("Jarvis, play music") is True
        assert detector.detect("hello there") is False

    def test_detect_custom_wake_word(self):
        detector = WakeWordDetector("computer")
        assert detector.detect("computer, start the music") is True
        assert detector.detect("jarvis, do something") is False


class TestVoiceService:
    def test_speak(self, config):
        service = VoiceService(config)
        with patch.object(service.tts, "synthesize", return_value="/tmp/test.wav"):
            result = service.speak("Hello")
            assert result == "/tmp/test.wav"

    def test_listen(self, config):
        service = VoiceService(config)
        with patch.object(service.stt, "transcribe", return_value="Hello world"):
            result = service.listen("test.wav")
            assert result == "Hello world"

    def test_is_wake_word(self, config):
        service = VoiceService(config)
        assert service.is_wake_word("jarvis, hello") is True
        assert service.is_wake_word("hello there") is False
