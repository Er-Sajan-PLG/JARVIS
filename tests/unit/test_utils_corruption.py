import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.utils.corruption import backup_corrupt_file

@patch("app.utils.corruption.datetime")
@patch("app.utils.corruption.Path")
def test_backup_corrupt_file_success(mock_path_class, mock_datetime):
    mock_now = MagicMock()
    mock_now.strftime.return_value = "20231026-123456"
    mock_datetime.now.return_value = mock_now

    mock_path_instance = MagicMock(spec=Path)
    mock_path_instance.name = "data.json"
    mock_path_class.return_value = mock_path_instance

    mock_backup_path = MagicMock(spec=Path)
    mock_path_instance.with_name.return_value = mock_backup_path

    result = backup_corrupt_file("dummy/path/data.json")

    mock_path_instance.with_name.assert_called_once_with("data.json.corrupt-20231026-123456.bak")
    mock_path_instance.replace.assert_called_once_with(mock_backup_path)
    assert result == mock_backup_path

@patch("app.utils.corruption.datetime")
@patch("app.utils.corruption.Path")
@patch("app.utils.corruption.shutil")
def test_backup_corrupt_file_fallback_copy(mock_shutil, mock_path_class, mock_datetime):
    mock_now = MagicMock()
    mock_now.strftime.return_value = "20231026-123456"
    mock_datetime.now.return_value = mock_now

    mock_path_instance = MagicMock(spec=Path)
    mock_path_instance.name = "data.json"
    mock_path_class.return_value = mock_path_instance

    mock_backup_path = MagicMock(spec=Path)
    mock_path_instance.with_name.return_value = mock_backup_path

    mock_path_instance.replace.side_effect = OSError("Cross-device link")

    result = backup_corrupt_file("dummy/path/data.json")

    mock_path_instance.with_name.assert_called_once_with("data.json.corrupt-20231026-123456.bak")
    mock_path_instance.replace.assert_called_once_with(mock_backup_path)
    mock_shutil.copy2.assert_called_once_with(mock_path_instance, mock_backup_path)
    assert result == mock_backup_path

@patch("app.utils.corruption.datetime")
@patch("app.utils.corruption.Path")
@patch("app.utils.corruption.shutil")
def test_backup_corrupt_file_total_failure(mock_shutil, mock_path_class, mock_datetime, caplog):
    mock_now = MagicMock()
    mock_now.strftime.return_value = "20231026-123456"
    mock_datetime.now.return_value = mock_now

    mock_path_instance = MagicMock(spec=Path)
    mock_path_instance.name = "data.json"
    mock_path_class.return_value = mock_path_instance

    mock_backup_path = MagicMock(spec=Path)
    mock_path_instance.with_name.return_value = mock_backup_path

    mock_path_instance.replace.side_effect = OSError("Cross-device link")
    mock_shutil.copy2.side_effect = OSError("Permission denied")

    with caplog.at_level(logging.WARNING):
        result = backup_corrupt_file("dummy/path/data.json")

    mock_path_instance.with_name.assert_called_once_with("data.json.corrupt-20231026-123456.bak")
    mock_path_instance.replace.assert_called_once_with(mock_backup_path)
    mock_shutil.copy2.assert_called_once_with(mock_path_instance, mock_backup_path)

    assert result is None
    assert "Could not back up corrupt file" in caplog.text
