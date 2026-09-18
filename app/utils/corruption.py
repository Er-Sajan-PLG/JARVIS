"""
Helpers for handling corrupted on-disk state.

When a JSON data file (memories, conversation, ...) fails to load, the naive
pattern is to silently swallow the error and start empty:

    except (json.JSONDecodeError, IOError):
        return

That hides data corruption from the operator AND lets the next ``save()``
overwrite the corrupt file, causing irreversible data loss with no signal.

These helpers instead:
  * quarantine the corrupt file to a timestamped ``.corrupt-*.bak`` backup so
    its bytes survive the next save, and
  * emit a loud, actionable warning.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path


def backup_corrupt_file(path) -> Path | None:
    """Quarantine *path* to a timestamped backup so its contents are not
    destroyed when the store later overwrites *path* with fresh data.

    Returns the backup path on success, or ``None`` if the backup could not
    be created. Any failure here is reported but never masks the original
    load error.
    """
    path = Path(path)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.corrupt-{timestamp}.bak")

    try:
        # Prefer a move (quarantine) so the corrupt file leaves the active
        # path; fall back to a copy if rename isn't possible (e.g. cross-device).
        try:
            path.replace(backup)
        except OSError:
            shutil.copy2(path, backup)
    except OSError as exc:
        logging.getLogger(__name__).warning("Could not back up corrupt file %s: %s", path, exc)
        return None
    return backup


def report_corruption(
    logger: logging.Logger,
    label: str,
    path,
    exc: Exception,
    backup: Path | None,
) -> None:
    """Emit a loud, actionable warning about a failed load.

    *label* is a human-readable name for what failed to load
    (e.g. ``"memories"`` / ``"conversation"``).
    """
    if backup is not None:
        backup_msg = f" The original file was quarantined to: {backup}"
    else:
        backup_msg = " WARNING: could not back up the file - data may be lost on the " "next save!"

    logger.error(
        "Failed to load %s from %s (%s: %s). Starting with an EMPTY %s.%s",
        label,
        path,
        type(exc).__name__,
        exc,
        label,
        backup_msg,
    )
