"""JARVIS Web API package.

Exposes a :func:`create_app` factory that builds a FastAPI application wrapping
the existing JARVIS conversation / memory / model pipeline and serves the
static web UI from the ``frontend/`` directory.

Run with::

    python -m app.api.server

Then open http://localhost:8000 in your browser.
"""

from app.api.server import create_app, run

__all__ = ["create_app", "run"]
