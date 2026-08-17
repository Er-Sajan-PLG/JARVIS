import pytest
from unittest.mock import patch
from pathlib import Path
from app.utils.corruption import backup_corrupt_file

def test_backup_corrupt_file_oserror(tmp_path, caplog):
    # Setup a dummy file
    test_file = tmp_path / "test.json"
    test_file.write_text("{}")

    # Mock Path.replace and shutil.copy2 to raise OSError
    with patch.object(Path, "replace", side_effect=OSError("replace failed")):
        with patch("app.utils.corruption.shutil.copy2", side_effect=OSError("copy failed")):
            result = backup_corrupt_file(test_file)

    assert result is None
    assert "Could not back up corrupt file" in caplog.text
