"""Doc coverage gate: every code surface must be documented, every documented
endpoint/env must exist. Fails loudly — this gate blocks commits and pushes.

Three censuses, all computed from the live tree (no hardcoded lists that rot):

1. MODULE COVERAGE — required code areas must appear in at least one doc's
   ``**Source**`` binding. A new module with zero docs fails the gate by
   construction (the blind spot that hid notify/voice/telegram/whatsapp,
   comms tools, mobile/, tgcall/).
2. ROUTE CENSUS — every served route (all APIRouter instances under
   ``app/adapters/`` + ``@app`` routes in ``app/main.py``) must be named in
   ``docs/API_CONTRACT.md``. Router files that only mount static assets are
   exempt via STATIC_MOUNTS.
3. ENV CENSUS — every ``os.getenv("X", ...)`` default read in ``app/`` must
   appear in ``docs/CONFIG.md``. Internal-only vars are exempt via
   ENV_ALLOWLIST (test hooks, Python internals).

Usage:
    .venv/bin/python scripts/check_doc_coverage.py          # human report
    .venv/bin/python scripts/check_doc_coverage.py --strict # exit 1 on findings

Tests in tests/unit/test_doc_coverage.py import the collectors so a single
missing doc fails the suite (and therefore the pipeline).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"

# Code areas that must be documented somewhere (prefix match on Source paths).
REQUIRED_SOURCES = [
    "app/adapters/web/router.py",
    "app/adapters/web/settings.py",
    "app/adapters/web/notify_routes.py",
    "app/adapters/web/voice_routes.py",
    "app/adapters/web/push_routes.py",
    "app/adapters/web/brief_routes.py",
    "app/adapters/web/email_routes.py",
    "app/adapters/http/router.py",
    "app/adapters/websocket/",
    "app/main.py",
    "app/bootstrap.py",
    "app/brain/",
    "app/tools/",
    "app/integrations/push/",
    "app/integrations/email/",
    "app/integrations/brief/",
    "app/integrations/telegram/",
    "app/integrations/whatsapp/",
    "app/integrations/voice/",
    "app/memory/",
    "app/models/",
    "app/guardrails/",
    "app/mcp/",
    "frontend/assets/",
    "frontend/index.html",
    "mobile/",
    "tgcall/",
    ".env.example",
]

# Router modules whose routes are static assets, not API endpoints.
STATIC_MOUNTS = {
    "app/main.py",  # PWA shell routes are pinned by test_mobile_pwa.py instead
}

# Env vars that need no CONFIG.md row (test/runtime internals, not operator config).
ENV_ALLOWLIST = {
    "PATH",
    "PYTHONPATH",
    "HOME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "VIRTUAL_ENV",
    "CONDA_DEFAULT_ENV",
    "NO_COLOR",
    "TERM",
    "CI",
    "GITHUB_ACTIONS",
    "PYTEST_CURRENT_TEST",
}

_SOURCE_RE = re.compile(r"^\s*\*\*Source\*\*\s*:\s*(.+)$", re.MULTILINE)


def collect_sources() -> set[str]:
    """All **Source** bindings across docs/** and root *.md."""
    found: set[str] = set()
    paths = list(DOCS.rglob("*.md"))
    paths += [p for p in REPO.glob("*.md") if p.is_file()]
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in _SOURCE_RE.finditer(text):
            raw = match.group(1).strip()
            # Source lines name several paths: `a`, `b` at HEAD. Collect every
            # backticked token, plus a bare leading token for old-style lines.
            for token in re.findall(r"`([^`]+)`", raw):
                token = token.strip().rstrip(",;")
                if token:
                    found.add(token)
            bare = re.sub(r"`[^`]*`", "", raw).strip().split()
            if bare and "/" in bare[0]:
                found.add(bare[0].rstrip(",;"))
    return found


def check_module_coverage(sources: set[str]) -> list[str]:
    """Required code areas with no doc Source binding.

    Containment runs both ways: a doc bound to ``app/adapters/`` covers
    ``app/adapters/web/router.py`` and vice versa. Without the reverse
    direction, broad architecture docs never satisfy the gate.
    """
    findings = []
    for required in REQUIRED_SOURCES:
        req = required.rstrip("/")
        hit = any(
            s == req or s.startswith(req + "/") or req.startswith(s.rstrip("/") + "/")
            for s in sources
        )
        if not hit:
            findings.append(f"undocumented code area: {required}")
    return findings


def _iter_router_files() -> list[Path]:
    adapters = REPO / "app" / "adapters"
    # "*router*" alone misses "*_routes.py" — the exact blind spot that hid
    # notify/voice/push/brief/email from every previous audit.
    files = sorted(adapters.rglob("*router*.py")) + sorted(adapters.rglob("*routes*.py"))
    return files + [REPO / "app" / "main.py"]


def _norm(path: str) -> str:
    # FastAPI converters ({model_id:path}) match the contract's {model_id}.
    path = re.sub(r"\{([A-Za-z_]+):[^}]+\}", r"{\1}", path)
    return path.rstrip("/") or "/"


def collect_routes() -> set[str]:
    """Route paths served by the app: prefix + @get/post/... paths per file.

    Only decorator calls count — a bare ``d.get("x")`` (dict, environ) is
    never a route. This killed a whole class of false positives.
    """
    routes: set[str] = set()
    for path in _iter_router_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        prefix = ""
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            is_router_ctor = (
                isinstance(node.func, ast.Name) and node.func.id == "APIRouter"
            ) or getattr(node.func, "attr", "") == "APIRouter"
            if is_router_ctor:
                for kw in node.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        prefix = str(kw.value.value)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for dec in node.decorator_list:
                if not (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr
                    in {
                        "get",
                        "post",
                        "put",
                        "patch",
                        "delete",
                        "head",
                        "options",
                        "websocket",
                    }
                ):
                    continue
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    routes.add(_norm(prefix + str(dec.args[0].value)))
    # Parameter segments ({email_id}) match any concrete value the contract names.
    return routes


def collect_contract_paths() -> set[str]:
    """Route-like paths named in docs/API_CONTRACT.md."""
    text = (DOCS / "API_CONTRACT.md").read_text(encoding="utf-8")
    found = set(re.findall(r"`((?:/[A-Za-z0-9_{}:.-]+)+/?)`", text))
    found |= set(re.findall(r"(?:GET|POST|PUT|PATCH|DELETE|HEAD) (/[A-Za-z0-9_{}/:.-]*)", text))
    return {_norm(p) for p in found if p.startswith("/")}


def _route_covered(route: str, contract: set[str]) -> bool:
    # /api/v1/emails/{email_id} is covered by /api/v1/emails/search-style rows
    # only when the contract names the concrete static routes; parameterised
    # routes must still appear literally (e.g. /{email_id}).
    return route.rstrip("/") in contract or route in contract


def check_route_census() -> list[str]:
    """Served routes missing from the API contract."""
    contract = collect_contract_paths()
    findings = []
    for route in sorted(collect_routes()):
        if _route_covered(route, contract):
            continue
        findings.append(f"route served but not in API_CONTRACT.md: {route}")
    return findings


def collect_env_vars() -> set[str]:
    """os.getenv / os.environ.get names defaulted anywhere under app/."""
    names: set[str] = set()
    for path in (REPO / "app").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_getenv = (
                isinstance(func, ast.Attribute)
                and func.attr in {"getenv", "get"}
                and isinstance(func.value, ast.Attribute)
                and func.value.attr == "environ"
            ) or (
                isinstance(func, ast.Attribute)
                and func.attr == "getenv"
                and getattr(func.value, "id", "") == "os"
            )
            if is_getenv and node.args and isinstance(node.args[0], ast.Constant):
                names.add(str(node.args[0].value))
    return names - ENV_ALLOWLIST


def check_env_census() -> list[str]:
    """Env vars read by code but absent from CONFIG.md."""
    text = (DOCS / "CONFIG.md").read_text(encoding="utf-8")
    return [
        f"env var read in app/ but not in CONFIG.md: {name}"
        for name in sorted(collect_env_vars())
        if name not in text
    ]


def run_all() -> list[str]:
    """All findings across the three censuses."""
    sources = collect_sources()
    return check_module_coverage(sources) + check_route_census() + check_env_census()


def main() -> int:
    findings = run_all()
    if not findings:
        print("doc coverage: modules, routes and env vars all documented")
        return 0
    print(f"doc coverage: {len(findings)} finding(s)")
    for finding in findings:
        print(f"  FAIL {finding}")
    return 1 if "--strict" in sys.argv else 0


if __name__ == "__main__":
    raise SystemExit(main())
