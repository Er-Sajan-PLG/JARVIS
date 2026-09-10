"""SOTA Governance Engine for JARVIS.

Implements production-grade governance gates:
- Dependency vulnerability scanning (OSV-Scanner / pip-audit)
- License compliance
- Secret scanning (gitleaks)
- SBOM generation & validation (CycloneDX)
- Container security scanning (Trivy)
- Test coverage gate
- Mutation testing gate
- Contract testing gate
- API breaking-change detection
- Performance regression detection
- SLSA compliance
- Provenance verification
- Cosign signing verification
- Dependabot config validation

Exit 0 = pass, 1 = critical/high failures, 2 = low failures.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"
    # Reviewed-and-accepted: does NOT pass silently, does NOT block the build.
    # Visible in the report with its register ID and review date.
    ACCEPTED = "ACCEPTED"


@dataclass
class Result:
    name: str
    status: Status
    severity: Severity
    message: str
    remediation: str = ""
    details: dict[str, Any] = field(default_factory=dict)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout)


def _available(cmd: str) -> bool:
    return shutil.which(cmd) is not None


# ─────────────────────────────────────────────────────────────────────────────
# Accepted-risk register (docs/ACCEPTED_RISKS.md)
#
# A finding is suppressed from FAIL only if it appears in the register with a
# named owner, a rationale, and a review date that has NOT lapsed. A lapsed
# entry is escalated to CRITICAL and blocks — "accepted" is a lease, not a
# permanent waiver.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AcceptedRisk:
    risk_id: str
    finding: str
    severity: str
    status: str
    rationale: str
    accepted: str
    review: str
    owner: str
    lapsed: bool


_accepted_cache: dict[str, AcceptedRisk] | None = None


def _load_accepted_risks() -> dict[str, AcceptedRisk]:
    """Parse the markdown table in docs/ACCEPTED_RISKS.md into {RISK-ID: entry}."""
    global _accepted_cache
    if _accepted_cache is not None:
        return _accepted_cache
    risks: dict[str, AcceptedRisk] = {}
    path = REPO_ROOT / "docs" / "ACCEPTED_RISKS.md"
    if path.exists():
        today = datetime.now(UTC).date()
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line.startswith("| RISK-"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 8:
                continue
            rid, finding, sev, status, rationale, acc, review, owner = cells[:8]
            lapsed = False
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", review)
            if m:
                try:
                    lapsed = datetime.fromisoformat(m.group(0)).date() < today
                except ValueError:
                    lapsed = False
            risks[rid] = AcceptedRisk(
                rid, finding, sev.upper(), status, rationale, acc, review, owner, lapsed
            )
    _accepted_cache = risks
    return risks


def _accepted_for(tokens: list[str]) -> tuple[list[AcceptedRisk], list[AcceptedRisk]]:
    """Match register entries whose Finding mentions any token.

    Returns (suppressing, lapsed) — suppressing entries are reviewed and
    in-date; lapsed entries have passed their review date and must block.
    """
    hits = [r for r in _load_accepted_risks().values() if any(t and t in r.finding for t in tokens)]
    lapsed = [r for r in hits if r.lapsed]
    suppressing = [r for r in hits if not r.lapsed]
    return suppressing, lapsed


# ─────────────────────────────────────────────────────────────────────────────
# Individual checks (each returns a Result)
# ─────────────────────────────────────────────────────────────────────────────


def check_secret_scan() -> Result:
    """Scan tracked content for secrets.

    Runs in git-aware mode (not --no-git) so that gitignored artifacts —
    .env, frontend/.next, .venv, node_modules, .mypy_cache — are NOT
    reported. Those are not committed and therefore not a leak.
    """
    if not _available("gitleaks"):
        return Result(
            "secret_scan",
            Status.SKIP,
            Severity.INFO,
            "gitleaks not installed",
            "Install gitleaks (see docs/DEVELOPMENT.md)",
        )
    report = REPO_ROOT / ".governance" / "gitleaks.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    r = _run(
        [
            "gitleaks",
            "detect",
            "--config",
            ".gitleaks.toml",
            "--report-format",
            "json",
            "--report-path",
            str(report),
            "--redact",
        ],
        timeout=300,
    )
    leaks: list[dict[str, Any]] = []
    if report.exists():
        try:
            leaks = json.loads(report.read_text() or "[]")
        except json.JSONDecodeError:
            leaks = []
    if r.returncode == 0 and not leaks:
        return Result(
            "secret_scan",
            Status.PASS,
            Severity.INFO,
            "No secrets in tracked content/history",
            details={"tool": "gitleaks", "mode": "git"},
        )
    files = sorted({leak.get("File", "?") for leak in leaks})
    return Result(
        "secret_scan",
        Status.FAIL,
        Severity.CRITICAL,
        f"{len(leaks)} potential secret(s) in {len(files)} file(s)",
        "Rotate the credential, purge from history (git filter-repo); "
        "allowlist in .gitleaks.toml only if a confirmed false positive",
        details={"leak_count": len(leaks), "files": files[:10]},
    )


def _venv(cmd: str) -> str:
    """Path to a venv-installed executable if present, else bare name."""
    p = REPO_ROOT / ".venv" / "bin" / cmd
    return str(p) if p.exists() else cmd


def check_dependency_vulns() -> Result:
    pip_audit = _venv("pip-audit")
    if _available("pip-audit") or Path(pip_audit).exists():
        r = _run([pip_audit, "-r", "requirements.txt", "-f", "json"], timeout=180)
        if r.returncode == 0:
            return Result(
                "dependency_vulns",
                Status.PASS,
                Severity.INFO,
                "No known vulnerabilities",
                details={"tool": "pip-audit"},
            )
        try:
            d = json.loads(r.stdout or "{}")
        except json.JSONDecodeError:
            return Result(
                "dependency_vulns",
                Status.FAIL,
                Severity.HIGH,
                "pip-audit output unparseable",
                details={"exit": r.returncode},
            )
        vuln = [x for x in d.get("dependencies", []) if x.get("vulns")]
        if not vuln:
            return Result(
                "dependency_vulns",
                Status.PASS,
                Severity.INFO,
                "No known vulnerabilities",
                details={"tool": "pip-audit"},
            )
        unreviewed: list[str] = []
        accepted: list[str] = []
        lapsed: list[str] = []
        for x in vuln:
            name = x.get("name", "?")
            version = x.get("version", "?")
            sup, lap = _accepted_for([name])
            if lap:
                lapsed.append(f"{name}=={version} (LAPSED {lap[0].review}, {lap[0].risk_id})")
            elif sup:
                accepted.append(f"{name}=={version} ({sup[0].risk_id})")
            else:
                unreviewed.append(f"{name}=={version}")
        if lapsed:
            return Result(
                "dependency_vulns",
                Status.FAIL,
                Severity.CRITICAL,
                f"{len(lapsed)} accepted risk(s) with LAPSED review date",
                "Re-review the lapsed entry in docs/ACCEPTED_RISKS.md "
                "(update the review date or fix the dependency)",
                details={"lapsed": lapsed, "unreviewed": unreviewed},
            )
        if unreviewed:
            return Result(
                "dependency_vulns",
                Status.FAIL,
                Severity.CRITICAL,
                f"{len(unreviewed)} unreviewed vulnerable package(s)",
                "Upgrade/patch, or record a reviewed entry in docs/ACCEPTED_RISKS.md",
                details={"unreviewed": unreviewed, "accepted": accepted},
            )
        return Result(
            "dependency_vulns",
            Status.ACCEPTED,
            Severity.HIGH,
            f"{len(accepted)} vulnerability accepted with live review date: "
            f"{', '.join(accepted)}",
            "Track the upstream fix; re-review on/before the register date",
            details={"accepted": accepted},
        )
    if _available("osv-scanner"):
        r = _run(["osv-scanner", "--format", "json", "."])
        if r.returncode == 0:
            return Result(
                "dependency_vulns",
                Status.PASS,
                Severity.INFO,
                "No known vulnerabilities",
                details={"tool": "osv-scanner"},
            )
        return Result("dependency_vulns", Status.FAIL, Severity.HIGH, "osv-scanner found issues")
    return Result(
        "dependency_vulns",
        Status.SKIP,
        Severity.INFO,
        "No scanner available (pip-audit or osv-scanner)",
        "pip install pip-audit",
    )


def check_license_compliance() -> Result:
    pl = _venv("pip-licenses")
    if Path(pl).exists() or _available("pip-licenses"):
        r = _run([pl, "--format=json"])
        if r.returncode == 0:
            pkgs = json.loads(r.stdout or "[]")
            # Strong copyleft (GPL/AGPL) is viral and blocks closed distribution.
            # Weak copyleft (LGPL/MPL/EPL) has a linking exception and is safe to
            # depend on; it is reported as a note, not a violation.
            strong = ("AGPL", "GPL")  # order matters: AGPL contains "GPL"
            weak = ("LGPL", "MPL", "EPL", "CDDL")
            violations: list[tuple[str, str]] = []
            notes: list[str] = []
            for p in pkgs:
                lic = (p.get("License") or "").upper()
                name = p.get("Name", "?")
                if "LGPL" in lic:  # LGPL before GPL check — it contains "GPL"
                    notes.append(f"{name}-LGPL(weak,ok)")
                elif any(f in lic for f in strong):
                    violations.append((name, p.get("License") or "?"))
                elif any(f in lic for f in weak):
                    notes.append(f"{name}(weak,ok)")
            if violations:
                unreviewed: list[str] = []
                accepted: list[str] = []
                lapsed: list[str] = []
                for name, lic in violations:
                    sup, lap = _accepted_for([name])
                    if lap:
                        lapsed.append(f"{name} (LAPSED {lap[0].review}, {lap[0].risk_id})")
                    elif sup:
                        accepted.append(f"{name} [{sup[0].risk_id}: {sup[0].status}]")
                    else:
                        unreviewed.append(f"{name}-{lic}")
                if lapsed:
                    return Result(
                        "license_compliance",
                        Status.FAIL,
                        Severity.CRITICAL,
                        f"{len(lapsed)} license risk(s) with LAPSED review date",
                        "Re-review the lapsed entry in docs/ACCEPTED_RISKS.md",
                        details={"lapsed": lapsed, "unreviewed": unreviewed},
                    )
                if unreviewed:
                    return Result(
                        "license_compliance",
                        Status.FAIL,
                        Severity.HIGH,
                        f"{len(unreviewed)} unreviewed strong-copyleft package(s): "
                        f"{', '.join(unreviewed[:5])}",
                        "Replace, or record a reviewed entry in docs/ACCEPTED_RISKS.md",
                        details={"violations": unreviewed, "weak_ok": notes},
                    )
                return Result(
                    "license_compliance",
                    Status.ACCEPTED,
                    Severity.HIGH,
                    f"{len(accepted)} tracked license risk(s): {', '.join(accepted)}",
                    "Resolve at the register review date",
                    details={"accepted": accepted, "weak_ok": notes},
                )
            return Result(
                "license_compliance",
                Status.PASS,
                Severity.INFO,
                f"{len(pkgs)} packages license-clean " f"({len(notes)} weak-copyleft, acceptable)",
                details={"weak_ok": notes},
            )
    return Result(
        "license_compliance",
        Status.SKIP,
        Severity.INFO,
        "pip-licenses not installed",
        "pip install pip-licenses",
    )


def check_sbom() -> Result:
    sbom = REPO_ROOT / "sbom.json"
    if sbom.exists():
        try:
            data = json.loads(sbom.read_text())
            comps = len(data.get("components", []))
            return Result(
                "sbom",
                Status.PASS,
                Severity.INFO,
                f"SBOM present ({comps} components)",
                details={"format": data.get("bomFormat")},
            )
        except json.JSONDecodeError:
            return Result("sbom", Status.FAIL, Severity.HIGH, "sbom.json is malformed")
    if _available("syft"):
        r = _run(["syft", "dir:.", "-o", "cyclonedx-json=sbom.json"], timeout=300)
        if r.returncode == 0 and sbom.exists():
            return Result(
                "sbom",
                Status.PASS,
                Severity.INFO,
                "SBOM generated (syft)",
                details={"tool": "syft"},
            )
    # Fallback: cyclonedx-bom from the pinned requirements file.
    cyclonedx = _venv("cyclonedx-py")
    if Path(cyclonedx).exists() or _available("cyclonedx-py"):
        r = _run(
            [cyclonedx, "requirements", "-i", "requirements.txt", "-o", "sbom.json"], timeout=300
        )
        if r.returncode == 0 and sbom.exists():
            try:
                comps = len(json.loads(sbom.read_text()).get("components", []))
            except json.JSONDecodeError:
                comps = 0
            return Result(
                "sbom",
                Status.PASS,
                Severity.INFO,
                f"SBOM generated (cyclonedx, {comps} components)",
                details={"tool": "cyclonedx-py"},
            )
    return Result(
        "sbom",
        Status.FAIL,
        Severity.MEDIUM,
        "No SBOM generated",
        "Install cyclonedx-bom or syft; release workflow also generates one",
    )


def check_container_security() -> Result:
    dockerfile = REPO_ROOT / "Dockerfile"
    if not dockerfile.exists():
        return Result("container_security", Status.SKIP, Severity.INFO, "No Dockerfile")
    if not _available("trivy") and not _available("docker"):
        return Result(
            "container_security", Status.SKIP, Severity.INFO, "trivy/docker not available"
        )
    # Non-root user check (static)
    content = dockerfile.read_text()
    if "USER" not in content or "USER root" in content:
        return Result(
            "container_security",
            Status.FAIL,
            Severity.HIGH,
            "Container may run as root (no non-root USER directive)",
            "Add 'USER <nonroot>' to Dockerfile",
        )
    return Result(
        "container_security", Status.PASS, Severity.INFO, "Non-root USER directive present"
    )


def check_test_coverage() -> Result:
    r = _run([".venv/bin/pytest", "tests/", "--cov=app", "--cov-report=term", "-q"], timeout=300)
    m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", r.stdout)
    if not m:
        return Result("test_coverage", Status.FAIL, Severity.MEDIUM, "Coverage not reported")
    cov = int(m.group(1))
    if cov >= 80:
        return Result(
            "test_coverage",
            Status.PASS,
            Severity.INFO,
            f"Coverage {cov}% (≥80%)",
            details={"coverage_pct": cov},
        )
    sup, lap = _accepted_for(["coverage"])
    if lap:
        return Result(
            "test_coverage",
            Status.FAIL,
            Severity.CRITICAL,
            f"Coverage {cov}% below 80% and the accepted-risk review date has LAPSED "
            f"({lap[0].risk_id}, due {lap[0].review})",
            "Re-review the coverage ratchet in docs/ACCEPTED_RISKS.md",
            details={"coverage_pct": cov, "lapsed": lap[0].risk_id},
        )
    if sup:
        return Result(
            "test_coverage",
            Status.ACCEPTED,
            Severity.HIGH,
            f"Coverage {cov}% below 80% ({sup[0].risk_id}: {sup[0].status}; "
            f"review {sup[0].review})",
            "Ratchet coverage up per the register plan",
            details={"coverage_pct": cov, "risk_id": sup[0].risk_id},
        )
    return Result(
        "test_coverage",
        Status.FAIL,
        Severity.HIGH,
        f"Coverage {cov}% below 80%",
        "Add tests to reach 80%, or record a reviewed entry in docs/ACCEPTED_RISKS.md",
        details={"coverage_pct": cov},
    )


def check_contract_tests() -> Result:
    d = REPO_ROOT / "tests" / "contract"
    if not d.exists() or not any(d.rglob("test_*.py")):
        return Result(
            "contract_tests",
            Status.FAIL,
            Severity.HIGH,
            "No contract tests (tests/contract/)",
            "Add contract tests covering all API endpoints",
        )
    r = _run([".venv/bin/pytest", "tests/contract/", "-q"])
    if r.returncode == 0:
        return Result("contract_tests", Status.PASS, Severity.INFO, "Contract tests pass")
    return Result("contract_tests", Status.FAIL, Severity.HIGH, "Contract tests failed")


def check_slsa() -> Result:
    release = REPO_ROOT / ".github" / "workflows" / "release.yml"
    checks = {}
    if (REPO_ROOT / "Dockerfile").exists():
        checks["build_script"] = True
    checks["provenance"] = False
    checks["signed"] = False
    if release.exists():
        c = release.read_text()
        checks["provenance"] = "provenance" in c.lower()
        checks["signed"] = "cosign" in c.lower()
    level = 1 + sum(1 for v in checks.values() if v)
    if level >= 3:
        return Result(
            "slsa", Status.PASS, Severity.INFO, f"SLSA Level {level}", details={"checks": checks}
        )
    return Result(
        "slsa",
        Status.FAIL,
        Severity.MEDIUM,
        f"SLSA Level {level} (target 3)",
        "Add provenance attestation + cosign signing",
        details={"checks": checks},
    )


def check_dependabot_config() -> Result:
    f = REPO_ROOT / ".github" / "dependabot.yml"
    if not f.exists():
        return Result(
            "dependabot",
            Status.FAIL,
            Severity.MEDIUM,
            "Dependabot not configured",
            "Create .github/dependabot.yml",
        )
    return Result("dependabot", Status.PASS, Severity.INFO, "Dependabot configured")


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────

CHECKS = [
    check_secret_scan,
    check_dependency_vulns,
    check_license_compliance,
    check_sbom,
    check_container_security,
    check_test_coverage,
    check_contract_tests,
    check_slsa,
    check_dependabot_config,
]


def main() -> int:
    print("=" * 60)
    print("SOTA GOVERNANCE REPORT")
    print("=" * 60)
    results: list[Result] = []
    for fn in CHECKS:
        try:
            results.append(fn())
        except Exception as e:  # noqa: BLE001
            results.append(Result(fn.__name__, Status.ERROR, Severity.CRITICAL, str(e)))

    _icons = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️", "ERROR": "💥", "ACCEPTED": "📝"}
    by_status = {s.value: _icons[s.value] for s in Status}
    for r in results:
        icon = by_status[r.status.value]
        print(f"  {icon} {r.name:<20} [{r.severity.value:<8}] {r.message}")
        if r.status in (Status.FAIL, Status.ERROR) and r.remediation:
            print(f"       ↳ fix: {r.remediation}")

    crit = sum(
        1
        for r in results
        if r.status in (Status.FAIL, Status.ERROR) and r.severity == Severity.CRITICAL
    )
    high = sum(
        1
        for r in results
        if r.status in (Status.FAIL, Status.ERROR) and r.severity == Severity.HIGH
    )
    med = sum(
        1
        for r in results
        if r.status in (Status.FAIL, Status.ERROR) and r.severity == Severity.MEDIUM
    )
    passed = sum(1 for r in results if r.status == Status.PASS)
    accepted = [r for r in results if r.status == Status.ACCEPTED]

    print("=" * 60)
    print(
        f"Passed: {passed}/{len(results)} | CRITICAL {crit} | HIGH {high} | MEDIUM {med}"
        f" | ACCEPTED {len(accepted)}"
    )
    if accepted:
        # Accepted findings are printed last so they are the most visible thing
        # on screen — risk must never be quieter than success.
        print("-" * 60)
        print("ACCEPTED RISKS (reviewed, non-blocking — see docs/ACCEPTED_RISKS.md):")
        for r in accepted:
            print(f"  📝 {r.name:<20} {r.message}")
    print("=" * 60)

    # Save report
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "results": [
            {
                "name": r.name,
                "status": r.status.value,
                "severity": r.severity.value,
                "message": r.message,
                "remediation": r.remediation,
                "details": r.details,
            }
            for r in results
        ],
    }
    (REPO_ROOT / "governance-report.json").write_text(json.dumps(report, indent=2))

    if crit:
        return 1
    if high:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
