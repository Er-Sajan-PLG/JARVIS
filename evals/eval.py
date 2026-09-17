"""Base types for the JARVIS eval suite (Sprint 3 capability contract).

An *eval* is a deterministic, self-contained check that runs in CI and reports
pass/fail with a score. No network, no wall-clock, no global state. Each eval is
an async callable returning an ``EvalResult``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvalStatus(str, Enum):
    """Outcome of an eval."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class EvalResult:
    """Result of a single eval."""

    name: str
    status: EvalStatus
    score: float = 1.0  # 0.0 .. 1.0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    @property
    def passed(self) -> bool:
        return self.status == EvalStatus.PASS


@dataclass
class EvalSuite:
    """A named collection of evals with aggregate results."""

    name: str
    results: list[EvalResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failed(self) -> list[EvalResult]:
        return [r for r in self.results if r.status == EvalStatus.FAIL]

    @property
    def score(self) -> float:
        if not self.results:
            return 1.0
        return sum(r.score for r in self.results) / len(self.results)
