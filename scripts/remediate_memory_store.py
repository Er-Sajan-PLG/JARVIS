"""One-shot remediation of the memory store.

Context: an audit of ``data/memories.json`` found 492 records that collapsed to
just 49 unique values (90% exact duplication). The cause is structural, not
cosmetic — ``MemoryService.store_memory()`` (the only path the web chat uses)
calls ``MemoryStore.add()``, which is a bare ``list.append`` with no duplicate
check, and never invokes the near-duplicate detector in ``app/memory/dedup.py``.

This script repairs the EXISTING data. The write-path fix is separate.

What it does, deterministically and reversibly:

1. **Normalizes** values (strips ANSI escapes, control bytes, and the
   ``[memory] stored ...`` pipeline-log tail that got captured as content).
2. **Drops pipeline junk** — records whose value is a log artifact.
3. **Drops conversation echoes** — the extractor stored both the user's probe
   AND the assistant's reply as facts ("ping", "default ok", "I am DeepSeek...").
   Test probes are not memories.
4. **Collapses exact duplicates**, keeping the earliest record and summing the
   useful counters.
5. **Quarantines the ``user_name: Alice`` poison** — 372 copies asserting the
   user is named Alice. It is preserved in the quarantine file for review, not
   silently deleted, because only the owner can confirm it is wrong.
6. **Writes a backup** before touching anything, and prints a full diff summary.

Run with ``--apply`` to write. Without it, prints the plan only (dry run).
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

STORE = Path("data/memories.json")
BACKUP_DIR = Path("data/backups")

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_LOG_TAIL = re.compile(r"\[memory\]\s*stored.*$", re.I | re.S)
_SEP_PREFIX = re.compile(r"^\[(pdf|jpg|jpeg|png|docx?|xlsx?|txt|csv)[^\]]*\]", re.I)

# The user's own probes against the assistant, stored as if they were facts.
_PROBE = re.compile(
    r"^(ping|pong|ok|okay|hello|hi|hey|test|testing|default ok|live ok|nvidia ok|"
    r"reply with exactly[:\s].*|say ok|tell me what is this file about\.?|"
    r"do you know( about)? me[.!?]*|what are you[.!?]*|"
    r"test memory for session|please remember.*|remember this.*)$",
    re.I,
)

# The assistant's own replies stored as user facts.
_ASSISTANT_ECHO = re.compile(
    r"^(i am|i'm|i don't|i do not|hello!|hi!|welcome,|certainly|sure[,!]|"
    r"great question|blue is a great|based on the content provided|"
    r"this file is|i don't see a file)",
    re.I,
)

# Assertions about who the user is that we cannot verify and that would poison
# an identity prompt. Quarantined, never auto-applied.
QUARANTINE_TYPES = {"user_name"}


def normalize(value: str) -> str:
    """Strip control noise and captured pipeline logs from a memory value."""
    v = _ANSI.sub("", str(value))
    v = "".join(c for c in v if c.isprintable() or c in " \t")
    v = _LOG_TAIL.sub("", v)
    v = re.sub(r"\s+", " ", v)
    return v.strip()


def classify(rec: dict[str, Any]) -> str:
    """Return why a record should go: 'junk' | 'probe' | 'echo' | 'keep'."""
    val = normalize(rec.get("value", ""))
    if not val or len(val) < 2:
        return "junk"
    if _LOG_TAIL.search(str(rec.get("value", ""))) and not val:
        return "junk"
    cat = rec.get("category", "")
    if cat in ("conversation",):
        # Whole category is probe/echo traffic in this store.
        return "probe"
    if _PROBE.match(val):
        return "probe"
    if _ASSISTANT_ECHO.match(val) and cat in ("conversation", "general"):
        return "echo"
    return "keep"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes")
    ap.add_argument("--store", default=str(STORE))
    args = ap.parse_args()

    path = Path(args.store)
    if not path.exists():
        print(f"no store at {path}", file=sys.stderr)
        return 1

    doc = json.loads(path.read_text(encoding="utf-8"))
    raw = doc.get("memories", [])
    print(f"store: {path}")
    print(f"records: {len(raw)}")

    kept: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    reasons: collections.Counter[str] = collections.Counter()
    merged_dupes = 0
    seen: dict[str, dict[str, Any]] = {}

    for rec in raw:
        # 1. Quarantine unverifiable identity assertions.
        if rec.get("type") in QUARANTINE_TYPES:
            quarantine.append({**rec, "value": normalize(rec.get("value", ""))})
            reasons["quarantined"] += 1
            continue

        # 2. Drop junk / probes / echoes.
        verdict = classify(rec)
        if verdict != "keep":
            reasons[verdict] += 1
            continue

        # 3. Collapse exact duplicates, keeping the earliest.
        norm = normalize(rec.get("value", ""))
        key = f"{rec.get('category','')}|{rec.get('type','')}|{norm.lower()}"
        if key in seen:
            first = seen[key]
            first["access_count"] = int(first.get("access_count", 0)) + int(
                rec.get("access_count", 0)
            )
            merged_dupes += 1
            continue
        clean = {**rec, "value": norm}
        seen[key] = clean
        kept.append(clean)

    print("\n=== plan ===")
    for reason, n in reasons.most_common():
        print(f"  {reason:14s} {n}")
    print(f"  {'merged dupes':14s} {merged_dupes}")
    print(f"  {'KEEP':14s} {len(kept)}")
    print(f"\n  {len(raw)} -> {len(kept)} records  ({len(raw)-len(kept)} removed)")

    print(f"\n=== records that will REMAIN ({len(kept)}) ===")
    bycat = collections.defaultdict(list)
    for r in kept:
        bycat[r.get("category", "?")].append(r)
    for cat in sorted(bycat, key=lambda c: -len(bycat[c])):
        print(f"\n  ── {cat} ({len(bycat[cat])})")
        for r in bycat[cat]:
            print(f"     [{r.get('type')}] {str(r.get('value'))[:84]}")

    if quarantine:
        print(f"\n=== QUARANTINED ({len(quarantine)}) — needs your confirmation ===")
        qc = collections.Counter(r.get("value") for r in quarantine)
        for v, n in qc.most_common(10):
            print(f"  x{n:4d}  type={quarantine[0].get('type')}  value={v!r}")

    if not args.apply:
        print("\n(dry run — pass --apply to write)")
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = BACKUP_DIR / f"memories-{stamp}.json"
    shutil.copy2(path, backup)
    print(f"\nbackup written: {backup}")

    doc["memories"] = kept
    doc["version"] = "2.1"
    doc["remediation"] = {
        "at": stamp,
        "removed": len(raw) - len(kept),
        "quarantined": len(quarantine),
        "merged_duplicates": merged_dupes,
        "reason": "collapse 90% duplication + drop probe/echo/log noise",
    }
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    qpath = BACKUP_DIR / f"memories-quarantine-{stamp}.json"
    qpath.write_text(json.dumps(quarantine, indent=2), encoding="utf-8")

    print(f"wrote {len(kept)} records to {path}")
    print(f"quarantined {len(quarantine)} to {qpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
