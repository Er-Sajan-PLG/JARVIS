"""JARVIS web API package.

The legacy ``app.api.server`` module was retired under ARCH-003: the HTTP surface now
lives in ``app/main.py`` + ``app/adapters/http/router.py``. It is therefore NOT
importable any more, by design — ``tests/sprint3/test_langgraph_engine_contract.py::
test_legacy_server_import_blocked`` asserts exactly that.

``app.api.ocr`` remains a live subpackage, so this ``__init__`` must stay importable
(it previously re-exported ``create_app``/``run`` from the archived module, which made
``import app.api`` raise ModuleNotFoundError).
"""
