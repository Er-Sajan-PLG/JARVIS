"""Temporal and provenance migration for the memory store.

Adds the ADR-015 fields to an existing store without destroying anything. This
is deliberately additive: every existing record keeps its value and gains
``valid_at``/``created_at`` from its original ``created_at``, so a pre-migration
store answers the same questions it did before, plus the new ones.

Run standalone (dry-run by default):

    .venv/bin/python scripts/migrate_memory_temporal.py
    .venv/bin/python scripts/migrate_memory_temporal.py --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

STORE = Path("data/memories.json")

# Facts whose truth is inherently time-bound. Used to seed valid_at/invalid_at
# from what the value itself states, so the migration does more than copy
# created_at into both clocks.
_ENDED_PATTERNS = (
    "aug 2024 to nov 2025",
    "aug 2025 to nov 2025",
    "2024-08 to 2025-11",
    "2025-08 to 2025-11",
    "dec 2023 to aug 2024",
    "jun 2023 to dec 2023",
    "2018-2023",
)


def _parse_month_year(text: str) -> float | None:
    """Parse a trailing 'Mon YYYY' / 'YYYY-MM' into epoch seconds, if present."""
    import re
    from datetime import UTC, datetime

    m = re.search(r"(\d{4})-(\d{2})", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1, tzinfo=UTC).timestamp()
        except ValueError:
            return None

    months = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})", text)
    if m:
        return datetime(int(m.group(2)), months[m.group(1)], 1, tzinfo=UTC).timestamp()
    return None


def _month_end(year: int, month: int) -> float:
    """Last day of a month, as a unix timestamp.

    Why this exists: a source that says "Aug 2025 to Nov 2025" states a
    MONTH-granularity end. Taking Nov 1 would claim the job ended on the 1st and
    make JARVIS understate a month of employment. The honest reading of "to Nov
    2025" is "through the end of November".
    """
    import calendar
    from datetime import UTC, datetime

    last = calendar.monthrange(year, month)[1]
    return datetime(year, month, last, tzinfo=UTC).timestamp()


def _derive_event_time(value: str) -> tuple[float | None, float | None]:
    """Extract (valid_at, invalid_at) from a value that states its own period.

    A record reading "RUCHI Developer ... Aug 2025 to Nov 2025" is true over a
    closed interval. Copying only created_at would claim it is current, which is
    false — the job ended.

    Month-granularity ends resolve to the LAST DAY of the month, never the first
    (see _month_end).
    """
    from datetime import UTC, datetime

    low = value.lower()
    import re

    m = re.search(r"(\w+ \d{4})\s+to\s+(\w+ \d{4})", low)
    if not m:
        m = re.search(r"\((\d{2}/\d{4})\s*-\s*(\d{2}/\d{4})\)", low)
        if m:

            def _mm_yyyy(s: str, end: bool = False) -> float | None:
                mm, yyyy = s.split("/")
                try:
                    return (
                        _month_end(int(yyyy), int(mm))
                        if end
                        else datetime(int(yyyy), int(mm), 1, tzinfo=UTC).timestamp()
                    )
                except ValueError:
                    return None

            start = _mm_yyyy(m.group(1))
            finish = _mm_yyyy(m.group(2), end=True)
            return start, finish

    if m:
        start = _parse_month_year(m.group(1))
        end_word = _parse_month_year(m.group(2))
        end = _month_end_from_ts(end_word) if end_word else None
        if start and end:
            return start, end

    # "2018-2023" style ranges.
    m = re.search(r"\b(19|20)\d{2}\s*-\s*((19|20)\d{2})\b", low)
    if m:
        y1 = int(m.group(0).split("-")[0])
        y2 = int(m.group(2))
        return (
            datetime(y1, 1, 1, tzinfo=UTC).timestamp(),
            datetime(y2, 12, 31, tzinfo=UTC).timestamp(),
        )
    return None, None


def _month_end_from_ts(ts: float) -> float:
    """Re-resolve a month-start timestamp to its month's last day."""
    from datetime import UTC, datetime

    dt = datetime.fromtimestamp(ts, UTC)
    return _month_end(dt.year, dt.month)


def migrate(apply: bool = False) -> dict[str, Any]:
    d = json.loads(STORE.read_text())
    ms = d["memories"]
    now = time.time()

    counts: dict[str, Any] = {
        "total": len(ms),
        "event_time_derived": 0,
        "event_instant": 0,
        "end_date_corrected": 0,
        "open": 0,
        "source_tagged": 0,
    }

    for m in ms:
        value = str(m.get("value") or "")

        # System time: created_at already exists for every record.
        if not m.get("created_at"):
            m["created_at"] = now

        # Event time: derive from the value when it states a period, else open.
        if "valid_at" not in m:
            v, inv = _derive_event_time(value)
            if v is not None or inv is not None:
                m["valid_at"] = v
                m["invalid_at"] = inv
                counts["event_time_derived"] += 1
            else:
                m["valid_at"] = None
                m["invalid_at"] = None
                counts["open"] += 1
        else:
            # Re-resolve an existing month-granularity END to the last day of
            # its month. The first version of this script stored Nov 1 for
            # "to Nov 2025", which understated employment by a month and made
            # JARVIS report the wrong leaving date. Idempotent: only rewrites
            # when the stored value actually differs.
            stale_end = m.get("invalid_at")
            if stale_end:
                fixed = _month_end_from_ts(float(stale_end))
                if fixed != stale_end:
                    m["invalid_at"] = fixed
                    counts["end_date_corrected"] += 1

        # occurs_at: the instant an EVENT happens. Parse it from the value when
        # the value states a time ("meeting on 2026-10-05 at 5pm"). Left absent
        # rather than guessed — a wrong reminder time is worse than none.
        if "occurs_at" not in m:
            from app.memory.temporal import parse_occurs_at

            stamped = parse_occurs_at(value)
            m["occurs_at"] = stamped
            if stamped is not None:
                counts["event_instant"] += 1

        # Provenance: prefer an existing metadata source, else infer from category.
        meta = m.get("metadata") or {}
        if not meta.get("source_document"):
            cat = str(m.get("category") or "")
            if "cv" in str(meta.get("source", "")).lower() or m.get("source") == "user":
                inferred = "owner statement"
            elif cat in ("library_document",):
                inferred = "uploaded document"
            else:
                inferred = str(m.get("source") or "unknown")
            meta["source_document"] = inferred
            m["metadata"] = meta
            counts["source_tagged"] += 1

        # Explicitly open-ended markers for the audit clock.
        m.setdefault("expired_at", None)
        m.setdefault("superseded_by", None)

    if apply:
        backup = Path("data/backups") / f"memories-premigrate-{time.strftime('%Y%m%d-%H%M%S')}.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(STORE, backup)
        STORE.write_text(json.dumps(d, indent=2))
        counts["backup"] = str(backup)

    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the migration (default: dry run)")
    args = ap.parse_args()

    counts = migrate(apply=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN (pass --apply to write)"
    print(f"=== temporal migration [{mode}] ===")
    for k, v in counts.items():
        print(f"  {k:22s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
