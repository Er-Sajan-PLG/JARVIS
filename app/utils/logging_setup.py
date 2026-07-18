"""
Centralized logging setup for JARVIS.

Most of the codebase already uses ``logging.getLogger(__name__)`` (see
``app/memory/store.py``, ``app/conversation/manager.py``,
``app/utils/corruption.py``). This module gives every other module a single,
consistent way to (a) obtain a namespaced logger and (b) configure root
logging once at process start.

Why a helper instead of ad-hoc ``print()``:
- Config-load warnings (e.g. in ``app.config.settings``) previously used
  ``print()``, which made them impossible to silence/redirect while debugging.
- A real logger respects levels and can be routed to a file or stderr.

UI-facing output (banners, the interactive model picker, streamed tokens)
stays as ``print()`` — that is deliberate user-facing text, not diagnostics.
"""

import logging

# One shared handler/format so all modules look consistent. Configured lazily
# by setup_logging() so importing this module has no side effects.
_configured = False

_DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO, fmt: str = _DEFAULT_FORMAT) -> None:
    """
    Configure root logging exactly once.

    Safe to call multiple times (idempotent): only the first call installs the
    handler. Subsequent calls are no-ops, so every module can call it without
    coordination.
    """
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a namespaced logger.

    Pass ``__name__`` from the calling module so logs read like
    ``app.config.settings`` instead of a bare root logger.
    """
    return logging.getLogger(name)
