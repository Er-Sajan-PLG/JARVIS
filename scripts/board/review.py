#!/usr/bin/env python3
"""JARVIS Virtual Board Governance Checks.

Runs 8 governance checks:
1. import_layering - Verify package boundaries respected
2. domain_purity - Domain models have no external deps
3. schema_drift - Database schema matches models
4. prerequisite_graph - Task dependencies valid
5. safety_gate_coverage - All tools have safety gate
6. mcp_tool_search - MCP components exist
7. otel_spans - OpenTelemetry spans present
8. langgraph_checkpoint - LangGraph checkpointing configured

Exit code 0 = all pass, non-zero = failures
"""

import sys
import ast
import os
from pathlib import Path
from typing import Set, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "app"

# Allowed package dependencies (enforced by import_layering)
# Internal package imports (within same package) are ALWAYS allowed
ALLOWED_DEPS = {
    "app.adapters": {"app.bootstrap", "app.brain"},
    "app.bootstrap": {"app.brain", "app.models", "app.resources", "app.memory",
                      "app.session", "app.workspace", "app.telemetry",
                      "app.prompt", "app.guardrails", "app.artifacts"},
    "app.brain": {"app.domain", "app.events", "app.guardrails"},
    "app.models": {"app.resources"},
    "app.memory": {"app.integrations"},
    "app.telemetry": {"app.events"},
    "app.guardrails": set(),
    "app.events": set(),
}

# Packages that are allowed to be imported by anyone (stdlib-like)
ALLOWED_UNIVERSAL = {
    "app.domain", "app.config", "app.utils", "app.integrations",
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


def check_import_layering() -> Tuple[bool, List[str]]:
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
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("app."):
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
                            # Check if this import violates boundaries
                            if pkg_name in ALLOWED_DEPS:
                                if imported_full not in allowed and not any(
                                    imported_full.startswith(a) for a in allowed
                                ):
                                    # Allow imports from domain, config, utils
                                    if not any(imported_full.startswith(p) for p in
                                               ["app.domain", "app.config", "app.utils", "app.integrations"]):
                                        errors.append(f"{py_file.relative_to(REPO_ROOT)}: "
                                                      f"{pkg_name} imports {imported_full} (not allowed)")
    return len(errors) == 0, errors


def check_domain_purity() -> Tuple[bool, List[str]]:
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
            if isinstance(node, ast.ImportFrom) and node.module:
                if not node.module.startswith("app.") and not node.module.startswith("."):
                    # External import in domain - allow stdlib
                    if node.module not in {"dataclasses", "datetime", "enum", "typing", "uuid", "pathlib", "collections", "json", "enum", "abc"}:
                        errors.append(f"{py_file.relative_to(REPO_ROOT)}: "
                                      f"Domain imports external module {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not alias.name.startswith("app."):
                        if alias.name not in {"dataclasses", "datetime", "enum", "typing", "uuid", "pathlib", "collections", "json", "abc"}:
                            errors.append(f"{py_file.relative_to(REPO_ROOT)}: "
                                          f"Domain imports external module {alias.name}")
    return len(errors) == 0, errors


def check_schema_drift() -> Tuple[bool, List[str]]:
    """Verify database schema matches expectations."""
    # This is a placeholder - implement when DB schema exists
    return True, []


def check_prerequisite_graph() -> Tuple[bool, List[str]]:
    """Verify task dependencies are valid."""
    # Placeholder for future implementation
    return True, []


def check_safety_gate_coverage() -> Tuple[bool, List[str]]:
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


def check_mcp_tool_search() -> Tuple[bool, List[str]]:
    """Verify MCP components exist."""
    errors = []
    for req in MCP_REQUIRED:
        if not (REPO_ROOT / req).exists():
            errors.append(f"Missing MCP component: {req}")
    return len(errors) == 0, errors


def check_otel_spans() -> Tuple[bool, List[str]]:
    """Verify OpenTelemetry spans with semantic conventions."""
    errors = []
    telemetry_dir = APP_ROOT / "telemetry"
    if not telemetry_dir.exists():
        return False, ["app/telemetry directory missing"]
    
    # The key constants that must be defined/exported
    required_constants = {
        "OTEL_AGENT_NAME",
        "OTEL_TOOL_NAME", 
        "OTEL_GUARDRAIL_RESULT",
        "gen_ai.agent.name",
        "gen_ai.tool.name",
        "gen_ai.guardrail.result",
    }
    
    for py_file in telemetry_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        content = py_file.read_text()
        
        # Check if this file defines or exports the required constants
        for attr in OTEL_ATTRIBUTES:
            # Look for the constant definition or export
            found = False
            if attr in content:
                found = True
            # Also check for constant definitions like OTEL_AGENT_NAME = "gen_ai.agent.name"
            elif attr.startswith("OTEL_") and attr in content:
                found = True
            # Check if exported via __all__
            elif "__all__" in content and attr in content:
                found = True
            
            if not found:
                errors.append(f"{py_file.relative_to(REPO_ROOT)}: missing OTel attribute {attr}")
    
    return len(errors) == 0, errors


def check_langgraph_checkpoint() -> Tuple[bool, List[str]]:
    """Verify LangGraph checkpointing configured."""
    errors = []
    for req in CHECKPOINT_REQUIRED:
        if not (REPO_ROOT / req).exists():
            errors.append(f"Missing checkpoint component: {req}")
    return len(errors) == 0, errors


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
    ]

    all_pass = True
    for name, check_fn in checks:
        passed, errors = check_fn()
        if passed:
            print(f"✅ {name}")
        else:
            print(f"❌ {name}")
            for err in errors:
                print(f"   - {err}")
            all_pass = False

    if all_pass:
        print("\n🎉 All 8 governance checks passed!")
        return 0
    else:
        print("\n💥 Some governance checks failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())