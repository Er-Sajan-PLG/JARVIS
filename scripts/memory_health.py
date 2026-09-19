#!/usr/bin/env python3
"""Read-only memory store health diagnostic (Sprint 10.3).

Reports counts, an exact-duplicate estimate, and pending quarantine state
without modifying anything. Exit 0 when healthy, 1 when the store looks
degraded (heavy duplication or stuck quarantine) so it can gate a cron.

Usage:
    .venv/bin/python scripts/memory_health.py
    .venv/bin/python scripts/memory_health.py --strict   # exit 1 on degradation
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

STORE = ROOT / "data" / "memories.json"
QUARANTINE_DIR = ROOT / "data" / "quarantine"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="exit 1 on degradation")
    args = parser.parse_args()

    if not STORE.is_file():
        print("memory store: missing (no data/memories.json)")
        return 0

    raw = json.loads(STORE.read_text(encoding="utf-8"))
    records = raw if isinstance(raw, list) else raw.get("memories", raw.get("records", []))
    total = len(records)

    values = [r.get("value", "") if isinstance(r, dict) else str(r) for r in records]
    unique = len(set(values))
    dup_ratio = 1.0 - (unique / total) if total else 0.0

    # Pending quarantine (poison/mark-as-suspect preserved for review).
    quarantine = 0
    for d in QUARANTINE_DIR.glob("*.json"):
        try:
            quarantine += len(json.loads(d.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            quarantine += 0

    print(f"memory store: {total} records, {unique} unique ({dup_ratio:.0%} duplicate)")
    print(f"quarantine: {quarantine} pending review")

    degraded = total > 0 and dup_ratio > 0.5
    if quarantine:
        degraded = True
    print("health:", "DEGRADED" if degraded else "OK")
    return 1 if degraded and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
