"""Terminal + JSON reporters for eval results."""

from __future__ import annotations

from evals.eval import EvalStatus, EvalSuite


def terminal_report(suite: EvalSuite) -> int:
    """Print an eval summary to stdout; return 0 on all-pass, 1 otherwise."""
    print(f"\n{'='*60}")
    print(f"EVAL SUITE: {suite.name}")
    print(f"{'='*60}")

    for result in suite.results:
        status_icon = {
            EvalStatus.PASS: "✅",
            EvalStatus.FAIL: "❌",
            EvalStatus.SKIP: "⏭",
        }[result.status]
        print(f"  {status_icon} {result.name:<35} {result.status.value:<4} {result.message}")

    print(f"{'─'*60}")
    total = len(suite.results)
    passed = sum(1 for r in suite.results if r.status == EvalStatus.PASS)
    failed = sum(1 for r in suite.results if r.status == EvalStatus.FAIL)
    skipped = sum(1 for r in suite.results if r.status == EvalStatus.SKIP)
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}  Skipped: {skipped}")
    print(f"Aggregate score: {suite.score:.2f}")
    print(f"{'='*60}\n")

    return 0 if suite.passed else 1


def json_report(suite: EvalSuite) -> dict:
    """Return the suite results as a JSON-serialisable dict."""
    return {
        "suite": suite.name,
        "passed": suite.passed,
        "score": suite.score,
        "total": len(suite.results),
        "results": [
            {
                "name": r.name,
                "status": r.status.value,
                "score": r.score,
                "message": r.message,
                "duration_ms": r.duration_ms,
                "details": r.details,
            }
            for r in suite.results
        ],
    }
