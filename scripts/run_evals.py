#!/usr/bin/env python3
"""Run the JARVIS eval suite from the terminal or CI."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so `evals` is importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.reporters import json_report, terminal_report
from evals.runner import run_suite


def main() -> int:
    ap = argparse.ArgumentParser(description="Run JARVIS eval suite")
    ap.add_argument("--json", action="store_true", help="output JSON instead of terminal")
    ap.add_argument("--suite", default="jarvis-suite", help="suite name")
    ap.add_argument("--package", default="evals.evals", help="package to scan for evals")
    args = ap.parse_args()

    suite = asyncio.run(run_suite(name=args.suite, package=args.package))

    if args.json:
        print(json.dumps(json_report(suite), indent=2))
    else:
        terminal_report(suite)

    return 0 if suite.passed else 1


if __name__ == "__main__":
    sys.exit(main())
