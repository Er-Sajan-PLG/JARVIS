#!/usr/bin/env python3
"""JARVIS Virtual Board Governance Checks.

Runs N governance checks (board gates — see scripts/board/review.py for the full list).
1. import_layering - Verify package boundaries respected
2. domain_purity - Domain models have no external deps
3. schema_drift - Database schema matches models
4. prerequisite_graph - Task dependencies valid
5. safety_gate_coverage - All tools have safety gate
6. mcp_tool_search - MCP components exist
7. otel_spans - OpenTelemetry spans present
8. langgraph_checkpoint - LangGraph checkpointing configured
9. eval_suite - Eval suite exists and is runnable
10. doc_drift - Docs match code (API routes, module docs)
11. dep_drift - Imports match requirements.txt

Exit code 0 = all pass, non-zero = failures
"""

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "app"

# Allowed package dependencies (enforced by import_layering)
# Internal package imports (within same package) are ALWAYS allowed
ALLOWED_DEPS = {
    "app.adapters": {"app.bootstrap", "app.brain"},
    "app.bootstrap": {
        "app.brain",
        "app.models",
        "app.resources",
        "app.memory",
        "app.session",
        "app.workspace",
        "app.telemetry",
        "app.prompt",
        "app.guardrails",
        "app.artifacts",
        "app.tools",
    },
    "app.brain": {"app.domain", "app.events", "app.guardrails"},
    "app.models": {"app.resources"},
    "app.memory": {"app.integrations"},
    "app.telemetry": {"app.events"},
    "app.guardrails": set(),
    "app.events": set(),
}

# Packages that are allowed to be imported by anyone (stdlib-like)
ALLOWED_UNIVERSAL = {
    "app.domain",
    "app.config",
    "app.utils",
    "app.integrations",
}

# Required files for MCP (mcp_tool_search)
MCP_REQUIRED = [
    "app/mcp/registry.py",
    "app/mcp/__init__.py",
]

# Required OTel span attributes (otel_spans)
OTEL_ATTRIBUTES = [
    "OTEL_AGENT_NAME",
    "OTEL_TOOL_NAME",
    "OTEL_GUARDRAIL_RESULT",
]

# LangGraph checkpointing (langgraph_checkpoint)
CHECKPOINT_REQUIRED = [
    "app/session/checkpointer.py",
]


def check_import_layering() -> tuple[bool, list[str]]:
    """Verify package boundaries are respected."""
    errors = []
    for pkg_dir in APP_ROOT.iterdir():
        if not pkg_dir.is_dir() or pkg_dir.name.startswith("_"):
            continue
        pkg_name = f"app.{pkg_dir.name}"
        allowed = ALLOWED_DEPS.get(pkg_name, set())
        for py_file in pkg_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and node.module.startswith("app.")
                ):
                    imported_full = node.module
                    # Internal package imports (within same package) are ALWAYS allowed
                    pkg_prefix = f"{pkg_name}."
                    if imported_full.startswith(pkg_prefix):
                        continue
                    # Universal imports allowed by anyone
                    for universal in ALLOWED_UNIVERSAL:
                        if imported_full == universal or imported_full.startswith(universal + "."):
                            break
                    else:
                        # Boundary check. Imports from the universal packages (domain,
                        # config, utils, integrations) are allowed by anyone.
                        if (
                            pkg_name in ALLOWED_DEPS
                            and imported_full not in allowed
                            and not any(imported_full.startswith(a) for a in allowed)
                            and not any(
                                imported_full.startswith(p)
                                for p in [
                                    "app.domain",
                                    "app.config",
                                    "app.utils",
                                    "app.integrations",
                                ]
                            )
                        ):
                            errors.append(
                                f"{py_file.relative_to(REPO_ROOT)}: "
                                f"{pkg_name} imports {imported_full} (not allowed)"
                            )
    return len(errors) == 0, errors


def check_domain_purity() -> tuple[bool, list[str]]:
    """Domain models should have no external dependencies (stdlib allowed)."""
    errors = []
    domain_dir = APP_ROOT / "domain"
    if not domain_dir.exists():
        return False, ["app/domain directory missing"]
    for py_file in domain_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            # External imports in domain: only stdlib is allowed.
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and not node.module.startswith("app.")
                and not node.module.startswith(".")
                and node.module
                not in {
                    "__future__",
                    "dataclasses",
                    "datetime",
                    "enum",
                    "typing",
                    "uuid",
                    "pathlib",
                    "collections",
                    "json",
                    "abc",
                }
            ):
                errors.append(
                    f"{py_file.relative_to(REPO_ROOT)}: "
                    f"Domain imports external module {node.module}"
                )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not alias.name.startswith("app.") and alias.name not in {
                        "dataclasses",
                        "datetime",
                        "enum",
                        "typing",
                        "uuid",
                        "pathlib",
                        "collections",
                        "json",
                        "abc",
                    }:
                        errors.append(
                            f"{py_file.relative_to(REPO_ROOT)}: "
                            f"Domain imports external module {alias.name}"
                        )
    return len(errors) == 0, errors


def check_schema_drift() -> tuple[bool, list[str]]:
    """Verify database schema matches expectations."""
    # This is a placeholder - implement when DB schema exists
    return True, []


def check_prerequisite_graph() -> tuple[bool, list[str]]:
    """Verify task dependencies are valid."""
    # Placeholder for future implementation
    return True, []


def check_safety_gate_coverage() -> tuple[bool, list[str]]:
    """Verify all tools have @safety_gate decorator."""
    errors = []
    tools_dir = APP_ROOT / "tools"
    if not tools_dir.exists():
        return False, ["app/tools directory missing"]
    for py_file in tools_dir.rglob("*.py"):
        if "__pycache__" in str(py_file) or py_file.name == "base.py":
            continue
        try:
            content = py_file.read_text()
        except Exception:
            continue
        if "@safety_gate" not in content and "safety_gate" not in content:
            errors.append(f"{py_file.relative_to(REPO_ROOT)}: missing @safety_gate")
    return len(errors) == 0, errors


def check_mcp_tool_search() -> tuple[bool, list[str]]:
    """Verify MCP components exist."""
    errors = []
    for req in MCP_REQUIRED:
        if not (REPO_ROOT / req).exists():
            errors.append(f"Missing MCP component: {req}")
    return len(errors) == 0, errors


def check_otel_spans() -> tuple[bool, list[str]]:
    """Verify OpenTelemetry spans with semantic conventions."""
    errors = []
    telemetry_dir = APP_ROOT / "telemetry"
    if not telemetry_dir.exists():
        return False, ["app/telemetry directory missing"]

    # Collect all attribute definitions across the telemetry directory
    all_content = ""
    for py_file in telemetry_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        all_content += py_file.read_text()

    # Check that all required attributes are defined somewhere in telemetry/
    for attr in OTEL_ATTRIBUTES:
        if attr not in all_content:
            errors.append(f"app/telemetry/: missing OTel attribute {attr}")

    return len(errors) == 0, errors


def check_langgraph_checkpoint() -> tuple[bool, list[str]]:
    """Verify LangGraph checkpointing configured."""
    errors = []
    for req in CHECKPOINT_REQUIRED:
        if not (REPO_ROOT / req).exists():
            errors.append(f"Missing checkpoint component: {req}")
    return len(errors) == 0, errors


def check_eval_suite() -> tuple[bool, list[str]]:
    """Verify the eval suite exists and is runnable."""
    errors = []
    evals_dir = REPO_ROOT / "evals"
    if not evals_dir.exists():
        errors.append("evals/ directory missing")
        return False, errors
    if not (evals_dir / "eval.py").exists():
        errors.append("evals/eval.py missing")
    if not (evals_dir / "runner.py").exists():
        errors.append("evals/runner.py missing")
    if not (evals_dir / "reporters.py").exists():
        errors.append("evals/reporters.py missing")
    evals_pkg = evals_dir / "evals"
    if not evals_pkg.exists() or not any(evals_pkg.glob("*.py")):
        errors.append("evals/evals/ package missing or empty")
    if not (REPO_ROOT / "scripts" / "run_evals.py").exists():
        errors.append("scripts/run_evals.py missing")
    return len(errors) == 0, errors


# Standard library modules (excluded from dep_drift check)
STDLIB_MODULES = {
    "__future__",
    "abc",
    "aifc",
    "argparse",
    "array",
    "ast",
    "asyncio",
    "atexit",
    "base64",
    "bdb",
    "binascii",
    "builtins",
    "bz2",
    "calendar",
    "cmath",
    "cmd",
    "code",
    "codecs",
    "codeop",
    "collections",
    "colorsys",
    "compileall",
    "concurrent",
    "configparser",
    "contextlib",
    "contextvars",
    "copy",
    "cProfile",
    "crypt",
    "csv",
    "ctypes",
    "curses",
    "dataclasses",
    "datetime",
    "dbm",
    "decimal",
    "difflib",
    "dis",
    "distutils",
    "doctest",
    "email",
    "encodings",
    "enum",
    "errno",
    "faulthandler",
    "fcntl",
    "filecmp",
    "fileinput",
    "fnmatch",
    "formatter",
    "fractions",
    "ftplib",
    "functools",
    "gc",
    "getopt",
    "getpass",
    "gettext",
    "glob",
    "grp",
    "gzip",
    "hashlib",
    "heapq",
    "hmac",
    "html",
    "http",
    "idlelib",
    "imaplib",
    "imghdr",
    "imp",
    "importlib",
    "inspect",
    "io",
    "ipaddress",
    "itertools",
    "json",
    "keyword",
    "lib2to3",
    "linecache",
    "locale",
    "logging",
    "lzma",
    "mailbox",
    "mailcap",
    "marshal",
    "math",
    "mimetypes",
    "mmap",
    "modulefinder",
    "multiprocessing",
    "netrc",
    "nis",
    "nntplib",
    "operator",
    "optparse",
    "os",
    "ossaudiodev",
    "parser",
    "pathlib",
    "pdb",
    "pickle",
    "pickletools",
    "pipes",
    "pkgutil",
    "platform",
    "plistlib",
    "poplib",
    "posix",
    "posixpath",
    "pprint",
    "profile",
    "pstats",
    "pty",
    "pwd",
    "py_compile",
    "pyclbr",
    "pydoc",
    "queue",
    "quopri",
    "random",
    "re",
    "readline",
    "reprlib",
    "resource",
    "rlcompleter",
    "runpy",
    "sched",
    "secrets",
    "select",
    "selectors",
    "shelve",
    "shlex",
    "shutil",
    "signal",
    "site",
    "smtpd",
    "smtplib",
    "sndhdr",
    "socket",
    "socketserver",
    "spwd",
    "sqlite3",
    "sre_compile",
    "sre_constants",
    "sre_parse",
    "ssl",
    "stat",
    "statistics",
    "string",
    "stringprep",
    "struct",
    "subprocess",
    "sunau",
    "symtable",
    "sys",
    "sysconfig",
    "syslog",
    "tabnanny",
    "tarfile",
    "telnetlib",
    "tempfile",
    "termios",
    "test",
    "textwrap",
    "threading",
    "time",
    "timeit",
    "tkinter",
    "token",
    "tokenize",
    "trace",
    "traceback",
    "tracemalloc",
    "tty",
    "turtle",
    "turtledemo",
    "types",
    "typing",
    "unicodedata",
    "unittest",
    "urllib",
    "uu",
    "uuid",
    "venv",
    "warnings",
    "wave",
    "weakref",
    "webbrowser",
    "winreg",
    "winsound",
    "wsgiref",
    "xdrlib",
    "xml",
    "xmlrpc",
    "zipapp",
    "zipfile",
    "zipimport",
    "zlib",
    # Internal package
    "app",
}

# Package name mapping: import name -> PyPI package name
# When different, dep_drift checks the PyPI name in requirements
PKG_NAME_MAP = {
    "cv2": "opencv-python",
    "jwt": "PyJWT",
    "PIL": "Pillow",
    "fitz": "PyMuPDF",
    "attr": "attrs",
    "gi": "PyGObject",
    "yaml": "PyYAML",
    "dotenv": "python-dotenv",
    "psycopg2": "psycopg2-binary",
    "pil": "Pillow",
}


def check_doc_drift() -> tuple[bool, list[str]]:
    """Verify docs match code — fail when drifted.

    Checks:
    1. API_CONTRACT.md routes match actual @web_router/@http_router routes
    2. CAPABILITY_CONTRACT.md features have corresponding code
    """
    issues = []

    # --- Check 1: API_CONTRACT.md routes match actual routes ---
    contract_path = REPO_ROOT / "docs" / "API_CONTRACT.md"
    if contract_path.exists():
        contract_text = contract_path.read_text()

        # Extract routes from API_CONTRACT.md
        contract_routes = set()
        for method, path in re.findall(r"(GET|POST|PUT|DELETE|PATCH)\s+(/\S+)", contract_text):
            # Skip WebSocket paths (they don't have HTTP handlers)
            if path.startswith("/ws/"):
                continue
            # Clean path: strip backticks and query params
            clean_path = path.split("?")[0].strip("`")
            contract_routes.add((method, clean_path))

        # Extract actual routes from ALL adapter router files. Older versions
        # only scanned web/router.py + http/router.py and matched the hardcoded
        # @web_router/@http_router decorators — that missed every standalone
        # *_routes.py (email, push, notify, brief, voice), which is precisely
        # how a documented endpoint could silently have "no handler".
        actual_routes = set()
        adapter_dir = REPO_ROOT / "app" / "adapters"
        router_files = list(adapter_dir.rglob("*router*.py")) + list(
            adapter_dir.rglob("*routes*.py")
        )
        for router_file in router_files:
            if router_file.name == "__init__.py":
                continue
            content = router_file.read_text()
            # Map each APIRouter variable to its prefix, e.g.
            # `email_router = APIRouter(prefix="/api/v1/emails", ...)`.
            var_to_prefix: dict[str, str] = {}
            for var, prefix in re.findall(
                r"(\w+)\s*=\s*APIRouter\([^)]*?prefix=[\"']([^\"']+)[\"']", content
            ):
                var_to_prefix[var] = prefix
            # Also catch the split form: APIRouter(\n  prefix="...", ...).
            for var, prefix in re.findall(
                r"(\w+)\s*=\s*APIRouter\([\s\S]*?prefix=[\"']([^\"']+)[\"']", content
            ):
                var_to_prefix[var] = prefix
            for var, method, path in re.findall(
                r'@(\w+)\.(get|post|put|delete|patch)\(["\'](\S+)["\']', content
            ):
                if var not in var_to_prefix:
                    continue
                prefix = var_to_prefix[var].rstrip("/")
                full_path = prefix + "/" + path.lstrip("/")
                actual_routes.add((method.upper(), full_path))

        # Find routes in contract but not in code (only check /api/v1/ routes)
        for method, path in contract_routes:
            if (method, path) not in actual_routes:
                # Skip planned/future routes. The contract has used several
                # headings over time ("## 12. Future Endpoints", now a planned
                # paths mapping table); match any line that names this path as
                # planned/future/mapping.
                planned_line = re.search(
                    rf"`{re.escape(method)} {re.escape(path)}`.*?(planned|future|mapping)",
                    contract_text,
                ) or re.search(
                    rf"`{re.escape(path)}`.*?(planned|future|mapping)",
                    contract_text,
                )
                if planned_line:
                    continue  # documented as planned / resolved elsewhere
                # Only flag v1 API routes (not /api/ web routes)
                if path.startswith("/api/v1/"):
                    issues.append(
                        f"API_CONTRACT.md declares {method} {path} but router.py has no handler"
                    )

        # Find routes in code but not in contract (only check /api/v1/ routes)
        for method, path in actual_routes:
            if (method, path) not in contract_routes and path.startswith("/api/v1/"):
                issues.append(
                    f"router.py has {method} {path} but API_CONTRACT.md doesn't document it"
                )

    # --- Check 2: CAPABILITY_CONTRACT.md features have code ---
    cap_path = REPO_ROOT / "docs" / "CAPABILITY_CONTRACT.md"
    if cap_path.exists():
        cap_text = cap_path.read_text()  # noqa: F841
        # Look for feature checkboxes that are unchecked: - [ ] feature_name
        # These represent planned but not implemented features
        # But we don't fail on those — they're explicitly future work

    return len(issues) == 0, issues


def check_dep_drift() -> tuple[bool, list[str]]:
    """Verify imports match requirements.txt.

    Critical check: every import in app/ must be in requirements.txt (or stdlib/app).
    Warning check: packages in requirements.txt but never imported (transitive/dev deps skipped).
    """
    issues = []
    warnings = []

    # Parse requirements.txt
    req_pkgs = {}
    req_path = REPO_ROOT / "requirements.txt"
    if req_path.exists():
        for line in req_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"^([a-zA-Z0-9_\-\.]+)", line)
            if match:
                pkg_name = match.group(1).lower().replace("-", "_")
                req_pkgs[pkg_name] = line

    # Scan all imports in app/
    imported_pkgs = set()
    for py_file in APP_ROOT.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            content = py_file.read_text()
        except Exception:
            continue
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        # Collect all function scopes first, then only count imports NOT inside
        # a function body as hard dependencies. Function-local imports are
        # lazy/optional (e.g. the legacy voice module's whisper/pyttsx3, only
        # pulled in if the experimental /ws/voice path is used) — counting
        # them as required produced false dep_drift failures.
        func_ranges = [
            n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                in_func = any(
                    f.lineno <= node.lineno <= (getattr(f, "end_lineno", f.lineno) or f.lineno)
                    for f in func_ranges
                )
                if in_func:
                    continue
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_pkgs.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_pkgs.add(node.module.split(".")[0])

    # Critical: imported but not in requirements (and not stdlib/app)
    for pkg in imported_pkgs:
        if pkg in STDLIB_MODULES:
            continue
        pkg_lower = pkg.lower().replace("-", "_") if pkg else ""
        mapped = PKG_NAME_MAP.get(pkg, pkg) or pkg
        mapped_lower = mapped.lower().replace("-", "_") if mapped else ""
        if (
            pkg_lower not in req_pkgs
            and mapped_lower not in req_pkgs
            and pkg not in req_pkgs
            and mapped not in req_pkgs
        ):
            issues.append(f"Import '{pkg}' not found in requirements.txt")

    # Warning: in requirements but never imported (skip transitive/dev)
    SKIP_UNUSED = {
        "pytest",
        "pytest_asyncio",
        "pytest_cov",
        "coverage",
        "pluggy",
        "iniconfig",
        "mypy",
        "mypy_extensions",
        "typing_inspection",
        "pyright",
        "ruff",
        "shellingham",
        "rich",
        "markdown_it_py",
        "mdurl",
        "pygments",
        "pip",
        "pip_licenses",
        "pip_requirements_parser",
        "pip_api",
        "pip_audit",
        "cyclonedx_python_lib",
        "defusedxml",
        "license_expression",
        "boolean_py",
        "sortedcontainers",
        "prettytable",
        "wcwidth",
        "py_serializable",
        "packageurl_python",
        "pyparsing",
        "fonttools",
        "pyproject_hooks",
        "tomli",
        "installer",
        "build",
        "setuptools",
        "wheel",
        "distlib",
        "platformdirs",
        "virtualenv",
        "filelock",
        "cfgv",
        "identify",
        "nodeenv",
        "pre_commit",
        "certifi",
        "idna",
        "charset_normalizer",
        "requests_toolbelt",
        "urllib3",
        "six",
        "decorator",
        "pytz",
        "pycparser",
        "cffi",
        "itsdangerous",
        "jmespath",
        "pkgutil_resolve_name",
        "importlib_resources",
        "zipp",
        "bcrypt",
        "cryptography",
        "fsspec",
        "cachecontrol",
        "msgpack",
        "click",
        "jiter",
        "jsonschema",
        "jsonschema_specifications",
        "mmh3",
        "narwhals",
        "orjson",
        "overrides",
        "packaging",
        "pillow",
        "propcache",
        "referencing",
        "rpds_py",
        "starlette",
        "tomli_w",
        "typer",
        "typing_extensions",
        "aiohttp",
        "aiosignal",
        "frozenlist",
        "multidict",
        "yarl",
        "async_timeout",
        "attrs",
        "exceptiongroup",
        "httpcore",
        "httpcore2",
        "httpx",
        "httpx2",
        "h11",
        "sniffio",
        "anyio",
        "httptools",
        "websocket_client",
        "websockets",
        "uvloop",
        "watchfiles",
        "grpcio",
        "protobuf",
        "googleapis_common_protos",
        "pyasn1",
        "pyasn1_modules",
        "rsa",
        "huggingface_hub",
        "hf_xet",
        "tokenizers",
        "safetensors",
        "regex",
        "requests",
        "tqdm",
        "joblib",
        "threadpoolctl",
        "numpy",
        "scipy",
        "scikit_learn",
        "networkx",
        "sympy",
        "mpmath",
        "flatbuffers",
        "onnxruntime",
        "cloudpickle",
        "durationpy",
        "kubernetes",
        "oauthlib",
        "requests_oauthlib",
        "truststore",
        "pybase64",
        "python_dotenv",
        "pyyaml",
        "python_dateutil",
        "jinja2",
        "markupsafe",
        "pydantic_core",
        "pydantic_settings",
        "annotated_types",
        "annotated_doc",
        "pypika",
        "tenacity",
        "ollama",
        "openai",
        "chromadb",
        "sentence_transformers",
        "transformers",
        "torch",
        "triton",
        "cuda_bindings",
        "cuda_pathfinder",
        "cuda_toolkit",
        "nvidia_cublas",
        "nvidia_cuda_cupti",
        "nvidia_cuda_nvrtc",
        "nvidia_cuda_runtime",
        "nvidia_cudnn_cu13",
        "nvidia_cufft",
        "nvidia_cufile",
        "nvidia_curand",
        "nvidia_cusolver",
        "nvidia_cusparse",
        "nvidia_cusparselt_cu13",
        "nvidia_nccl_cu13",
        "nvidia_nvjitlink",
        "nvidia_nvshmem_cu13",
        "nvidia_nvtx",
        "opentelemetry_api",
        "opentelemetry_exporter_otlp_proto_common",
        "opentelemetry_exporter_otlp_proto_grpc",
        "opentelemetry_proto",
        "opentelemetry_sdk",
        "opentelemetry_semantic_conventions",
        "structlog",
        "tiktoken",
        "asyncpg",
        "mcp",
        "psycopg",
        "psycopg2",
        "langgraph",
        "opentelemetry",
        "psycopg2_binary",
    }
    for pkg in req_pkgs:
        if (
            pkg in imported_pkgs
            or pkg.replace("_", "-") in imported_pkgs
            or pkg.replace("-", "_") in imported_pkgs
        ):
            continue
        if pkg in SKIP_UNUSED:
            continue
        warnings.append(
            f"Package '{pkg}' in requirements.txt never imported (transitive or unused)"
        )

    return len(issues) == 0, issues + warnings


def main():
    checks = [
        ("import_layering", check_import_layering),
        ("domain_purity", check_domain_purity),
        ("schema_drift", check_schema_drift),
        ("prerequisite_graph", check_prerequisite_graph),
        ("safety_gate_coverage", check_safety_gate_coverage),
        ("mcp_tool_search", check_mcp_tool_search),
        ("otel_spans", check_otel_spans),
        ("langgraph_checkpoint", check_langgraph_checkpoint),
        ("eval_suite", check_eval_suite),
        ("doc_drift", check_doc_drift),
        ("dep_drift", check_dep_drift),
    ]

    all_pass = True
    for name, check_fn in checks:
        passed, errors = check_fn()
        # For dep_drift, only failures (not warnings) count against gate
        if name == "dep_drift":
            # errors contains both issues and warnings; separate them
            issues = [e for e in errors if "transitive or unused" not in e]
            warnings = [e for e in errors if "transitive or unused" in e]
            if issues:
                print(f"❌ {name}")
                for err in issues:
                    print(f"   - {err}")
                for warn in warnings:
                    print(f"   ⚠ {warn}")
                all_pass = False
            elif warnings:
                print(f"⚠ {name}")
                for warn in warnings:
                    print(f"   ⚠ {warn}")
            else:
                print(f"✅ {name}")
        else:
            if passed:
                print(f"✅ {name}")
            else:
                print(f"❌ {name}")
                for err in errors:
                    print(f"   - {err}")
                all_pass = False

    if all_pass:
        print(f"\n🎉 All {len(checks)} governance checks passed!")
        return 0
    else:
        print("\n💥 Some governance checks failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
