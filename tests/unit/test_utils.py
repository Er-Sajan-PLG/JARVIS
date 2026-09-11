"""Unit tests for app/utils modules:
server_manager, tokenizer, corruption, image, logging_setup, text.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.config.settings import ModelConfig, Settings
from app.utils.corruption import backup_corrupt_file, report_corruption
from app.utils.image import get_image_info, is_supported_image, validate_image
from app.utils.logging_setup import get_logger, setup_logging
from app.utils.server_manager import (
    ensure_server_running,
    find_llama_server_binary,
    is_local_url,
    is_port_open,
    llamacpp_live_models,
    match_ollama_model,
    ollama_model_names,
    port_from_url,
    warn_if_missing,
)
from app.utils.text import extract_keywords
from app.utils.tokenizer import (
    _word_counter,
    count_tokens,
    estimate_tokens,
    get_tokenizer_info,
)

# --- Corruption Tests ---


def test_backup_corrupt_file_success(tmp_path: Path) -> None:
    bad_file = tmp_path / "corrupt.json"
    bad_file.write_text("{broken json", encoding="utf-8")

    backup = backup_corrupt_file(bad_file)
    assert backup is not None
    assert backup.exists()
    assert ".corrupt-" in backup.name
    assert not bad_file.exists()


def test_backup_corrupt_file_fallback_copy(tmp_path: Path) -> None:
    bad_file = tmp_path / "corrupt_copy.json"
    bad_file.write_text("{broken", encoding="utf-8")

    # Force replace to fail with OSError so it falls back to shutil.copy2
    with patch.object(Path, "replace", side_effect=OSError("Cross-device link")):
        backup = backup_corrupt_file(bad_file)
        assert backup is not None
        assert backup.exists()


def test_backup_corrupt_file_failure(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.json"
    backup = backup_corrupt_file(missing_file)
    assert backup is None


def test_report_corruption(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("test_logger")
    with caplog.at_level(logging.ERROR):
        # With backup
        report_corruption(
            logger,
            "test_data",
            "/path/to/file",
            ValueError("Decode failed"),
            Path("/path/to/file.bak"),
        )
        assert "quarantined to: /path/to/file.bak" in caplog.text

        # Without backup
        report_corruption(logger, "test_data", "/path/to/file", ValueError("Decode failed"), None)
        assert "could not back up the file" in caplog.text


# --- Logging Setup Tests ---


def test_logging_setup() -> None:
    logger = get_logger("app.custom.module")
    assert logger.name == "app.custom.module"

    # Multiple calls are idempotent
    setup_logging(level=logging.DEBUG)
    setup_logging(level=logging.INFO)


# --- Text Helpers Tests ---


def test_extract_keywords() -> None:
    assert extract_keywords("") == set()
    text = "The quick brown Fox jumps over a lazy Dog! 123"
    keywords = extract_keywords(text)
    # Stop words ('the', 'over', 'a') and single letters should be dropped
    assert "fox" in keywords
    assert "quick" in keywords
    assert "brown" in keywords
    assert "lazy" in keywords
    assert "dog" in keywords
    assert "the" not in keywords
    assert "a" not in keywords


# --- Tokenizer Tests ---


def test_word_counter() -> None:
    assert _word_counter("") == 0
    c1 = _word_counter("Hello world")
    assert c1 > 0
    c2 = _word_counter("Hello world this is a slightly longer sentence for testing.")
    assert c2 > c1


def test_estimate_tokens_methods() -> None:
    text = "Jarvis cognitive architecture system"
    assert estimate_tokens("", method="auto") == 0
    assert estimate_tokens(text, method="word") > 0
    assert estimate_tokens(text, method="tiktoken") > 0
    assert estimate_tokens(text, method="transformers") > 0
    assert estimate_tokens(text, method="auto") > 0
    assert count_tokens(text) > 0


def test_get_tokenizer_info() -> None:
    info = get_tokenizer_info()
    assert "tiktoken_available" in info
    assert "transformers_available" in info
    assert "active_method" in info
    assert info["test_count"] > 0


# --- Image Utilities Tests ---


def test_is_supported_image() -> None:
    assert is_supported_image("test.png") is True
    assert is_supported_image("photo.JPEG") is True
    assert is_supported_image("pic.webp") is True
    assert is_supported_image("document.pdf") is False
    assert is_supported_image("code.py") is False


def test_validate_and_get_image_info(tmp_path: Path) -> None:
    img_path = tmp_path / "valid.png"
    # Create valid 10x10 PNG image
    img = Image.new("RGB", (10, 10), color="blue")
    img.save(img_path, format="PNG")

    valid, err = validate_image(str(img_path))
    assert valid is True
    assert err == ""

    info = get_image_info(str(img_path))
    assert info["width"] == 10
    assert info["height"] == 10
    assert info["format"] == "PNG"

    # Corrupt image
    bad_img_path = tmp_path / "corrupt.png"
    bad_img_path.write_bytes(b"not an image")
    valid_bad, err_bad = validate_image(str(bad_img_path))
    assert valid_bad is False
    assert err_bad != ""


# --- Server Manager Tests ---


def test_port_from_url() -> None:
    assert port_from_url("http://localhost:8080/v1") == 8080
    assert port_from_url("https://api.openai.com/v1") == 443
    assert port_from_url("http://example.com/api") == 80


def test_is_local_url() -> None:
    assert is_local_url("http://localhost:8080") is True
    assert is_local_url("http://127.0.0.1:8080") is True
    assert is_local_url("http:///test") is True
    assert is_local_url("https://api.groq.com/v1") is False


def test_is_port_open() -> None:
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__.return_value = mock_sock

        mock_sock.connect_ex.return_value = 0
        assert is_port_open(8080) is True

        mock_sock.connect_ex.return_value = 111
        assert is_port_open(8080) is False


def test_find_llama_server_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 1. Environment variable override
    monkeypatch.setenv("LLAMA_SERVER_PATH", "/custom/bin/llama-server")
    assert find_llama_server_binary() == "/custom/bin/llama-server"

    monkeypatch.delenv("LLAMA_SERVER_PATH", raising=False)

    # 2. PATH lookup
    with patch("shutil.which", return_value="/usr/local/bin/llama-server"):
        assert find_llama_server_binary() == "/usr/local/bin/llama-server"

    # 3. Local dir lookup
    with patch("shutil.which", return_value=None):
        monkeypatch.chdir(tmp_path)
        local_bin = tmp_path / "llama-server"
        assert find_llama_server_binary() is None
        local_bin.touch()
        assert find_llama_server_binary() == str(local_bin)


def test_ollama_model_names() -> None:
    with patch("requests.get") as mock_get:
        # Success response
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [{"name": "llama3:latest"}, {"name": "nomic-embed"}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        models = ollama_model_names("http://localhost:11434")
        assert models == ["llama3:latest", "nomic-embed"]

        # Failure / down response
        mock_get.side_effect = Exception("Connection refused")
        assert ollama_model_names("http://localhost:11434") == []


def test_match_ollama_model() -> None:
    available = ["qwen3:8b", "llama3:8b", "nomic-embed-text:latest"]
    assert match_ollama_model("qwen3-8b.gguf", available) == "qwen3:8b"
    assert match_ollama_model("llama3-8b.gguf", available) == "llama3:8b"
    assert match_ollama_model("unknown.gguf", available) is None


def test_ensure_server_running() -> None:
    # Case 1: Already running
    with patch("app.utils.server_manager.is_port_open", return_value=True):
        assert ensure_server_running(8080, ["llama-server"]) is True

    # Case 2: Binary not found
    with (
        patch("app.utils.server_manager.is_port_open", return_value=False),
        patch("shutil.which", return_value=None),
        patch("os.path.exists", return_value=False),
    ):
        assert ensure_server_running(8080, ["non_existent_binary"]) is False

    # Case 3: Successfully launched and booted
    with (
        patch("app.utils.server_manager.is_port_open", side_effect=[False, True]),
        patch("shutil.which", return_value="/bin/server"),
        patch("subprocess.Popen") as mock_popen,
        patch("time.sleep"),
    ):
        assert ensure_server_running(8080, ["/bin/server"], timeout=2) is True
        mock_popen.assert_called_once()

    # Case 4: Launch exception
    with (
        patch("app.utils.server_manager.is_port_open", return_value=False),
        patch("shutil.which", return_value="/bin/server"),
        patch("subprocess.Popen", side_effect=OSError("Exec format error")),
    ):
        assert ensure_server_running(8080, ["/bin/server"]) is False

    # Case 5: Timed out waiting
    with (
        patch("app.utils.server_manager.is_port_open", return_value=False),
        patch("shutil.which", return_value="/bin/server"),
        patch("subprocess.Popen"),
        patch("time.sleep"),
    ):
        assert ensure_server_running(8080, ["/bin/server"], timeout=1) is False


def test_llamacpp_live_models() -> None:
    settings = Settings(
        models={
            "local1": ModelConfig(
                name="m1", role="chat", backend="llamacpp", base_url="http://localhost:8080/v1"
            ),
            "remote": ModelConfig(
                name="m2", role="chat", backend="llamacpp", base_url="https://api.openai.com/v1"
            ),
            "other_backend": ModelConfig(
                name="m3", role="chat", backend="groq", base_url="http://localhost:8081/v1"
            ),
            "local2": ModelConfig(
                name="m4", role="embed", backend="llamacpp", base_url="http://localhost:8082/v1"
            ),
        }
    )

    def port_mock(port: int, host: str = "localhost") -> bool:
        return port == 8080

    with patch("app.utils.server_manager.is_port_open", side_effect=port_mock):
        live = llamacpp_live_models(settings)
        assert len(live) == 1
        assert live[0]["key"] == "local1"
        assert live[0]["base_url"] == "http://localhost:8080/v1"


def test_warn_if_missing() -> None:
    with patch("app.utils.server_manager.is_port_open", return_value=True):
        assert warn_if_missing("http://localhost:11434", "Ollama") is True

    with patch("app.utils.server_manager.is_port_open", return_value=False):
        assert warn_if_missing("http://localhost:11434", "Ollama") is False
