import socket
from unittest.mock import patch

from app.utils.server_manager import is_port_open

def test_is_port_open_true_with_real_socket():
    # Bind to an ephemeral port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        _, port = s.getsockname()

        assert is_port_open(port, "127.0.0.1") is True

def test_is_port_open_false_with_real_socket():
    # Bind and immediately close to ensure the port is not listening
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        _, port = s.getsockname()

    # Now s is closed, so the port should not be open
    assert is_port_open(port, "127.0.0.1") is False

@patch("app.utils.server_manager.socket.socket")
def test_is_port_open_mock_true(mock_socket_class):
    mock_socket_instance = mock_socket_class.return_value.__enter__.return_value
    mock_socket_instance.connect_ex.return_value = 0

    assert is_port_open(8080, "localhost") is True
    mock_socket_instance.connect_ex.assert_called_once_with(("localhost", 8080))
    mock_socket_instance.settimeout.assert_called_once_with(1)

@patch("app.utils.server_manager.socket.socket")
def test_is_port_open_mock_false(mock_socket_class):
    mock_socket_instance = mock_socket_class.return_value.__enter__.return_value
    mock_socket_instance.connect_ex.return_value = 111 # Connection refused

    assert is_port_open(8080, "localhost") is False
    mock_socket_instance.connect_ex.assert_called_once_with(("localhost", 8080))
    mock_socket_instance.settimeout.assert_called_once_with(1)
