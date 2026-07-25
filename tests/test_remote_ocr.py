import pytest

from unittest.mock import Mock

from app.knowledge.extract import RemoteOCREngine


def test_remote_ocr_requests_success(monkeypatch):
    # Simulate requests.post returning a JSON payload
    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.json = Mock(return_value={"text": "Recognized text"})

    mock_requests = Mock()
    mock_requests.post = Mock(return_value=mock_resp)

    monkeypatch.setitem(__import__('sys').modules, 'requests', mock_requests)

    eng = RemoteOCREngine(url="http://example.local/ocr/process")
    text = eng.ocr_image(b"PNGBYTES")
    assert text == "Recognized text"


def test_remote_ocr_no_url_raises():
    eng = RemoteOCREngine(url="")
    with pytest.raises(RuntimeError):
        eng.ocr_image(b"data")
