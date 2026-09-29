#!/usr/bin/env python3
"""Deliver the morning brief (Sprint 9.3).

Usage:
    .venv/bin/python scripts/deliver_brief.py [--channel push] [--channel telegram] ...

Defaults to the channels configured in JARVIS_BRIEF_DELIVERY. Exit 0 only when
at least one channel reported success — a timer that fails loudly is better
than one that silently never delivered.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env so a manual run sees the same config the timer's EnvironmentFile does.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO)


async def main() -> int:
    from app.integrations.brief import BriefConfig, BriefService

    parser = argparse.ArgumentParser(description="Deliver the JARVIS morning brief")
    parser.add_argument("--channel", action="append", dest="channels")
    args = parser.parse_args()

    cfg = BriefConfig.from_env()
    if args.channels:
        cfg.delivery_channels = args.channels

    service = BriefService(cfg)
    brief = await service.generate_brief()
    results = await service.deliver(brief)

    ok = [c for c, r in results.items() if isinstance(r, dict) and r.get("success")]
    ok += [c for c, r in results.items() if r is True]
    # Report the outcome, not the attempt. This line previously printed
    # "brief delivered: {...}" unconditionally, so the journal recorded success
    # one second before the unit exited 1 -- which is why a daily failure went
    # unnoticed. The exit code was always honest; only the log line lied.
    if ok:
        print(f"brief delivered via {ok}: {results}")
    else:
        print(f"brief NOT delivered, no channel succeeded: {results}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
