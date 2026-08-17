import os
from unittest.mock import patch

from app.utils.server_manager import find_llama_server_binary


@patch("app.utils.server_manager.os.environ.get")
def test_find_llama_server_binary_override(mock_env_get):
    mock_env_get.return_value = "/custom/path/llama-server"
    assert find_llama_server_binary() == "/custom/path/llama-server"
    mock_env_get.assert_called_once_with("LLAMA_SERVER_PATH")


@patch("app.utils.server_manager.os.environ.get")
@patch("app.utils.server_manager.shutil.which")
def test_find_llama_server_binary_which(mock_which, mock_env_get):
    mock_env_get.return_value = None
    mock_which.return_value = "/usr/bin/llama-server"

    assert find_llama_server_binary() == "/usr/bin/llama-server"
    mock_which.assert_called_once_with("llama-server")


@patch("app.utils.server_manager.os.environ.get")
@patch("app.utils.server_manager.shutil.which")
@patch("app.utils.server_manager.os.getcwd")
@patch("app.utils.server_manager.os.path.exists")
def test_find_llama_server_binary_local(mock_exists, mock_getcwd, mock_which, mock_env_get):
    mock_env_get.return_value = None
    mock_which.return_value = None
    mock_getcwd.return_value = "/project/root"
    mock_exists.return_value = True

    assert find_llama_server_binary() == "/project/root/llama-server"

    mock_which.assert_called_once_with("llama-server")
    mock_exists.assert_called_once_with(os.path.join("/project/root", "llama-server"))


@patch("app.utils.server_manager.os.environ.get")
@patch("app.utils.server_manager.shutil.which")
@patch("app.utils.server_manager.os.path.exists")
def test_find_llama_server_binary_not_found(mock_exists, mock_which, mock_env_get):
    mock_env_get.return_value = None
    mock_which.return_value = None
    mock_exists.return_value = False

    assert find_llama_server_binary() is None

    mock_which.assert_called_once_with("llama-server")
    mock_exists.assert_called_once()
