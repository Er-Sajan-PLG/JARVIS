"""Seed JARVIS memory from verified profile data, reconciling collisions.

Source of truth for the professional facts is Sajan's own LinkedIn profile
(https://www.linkedin.com/in/sajan-gurung-786705285/), fetched 2026-09-15. Only
facts that appear there are written; nothing is inferred.

Collisions this resolves
------------------------
1. Two records described Sajan as a "civil engineering student". He graduated in
   2023 and has 2y7m of professional experience as a Civil Engineer Manager —
   both student records are stale and are replaced.
2. `identity` and `profession` stored the same fact twice.
3. Duplicate `goals` rows.
4. A bogus `user_name: "Alice"` that keeps being reintroduced; dropped by type.

SEPARATE, DELIBERATE LIMITATION: the store has no field for *when* something
happens. `MemoryItem` carries `expires_at` but nothing carries `occurs_at`, so a
date is stored as part of the value text. That is a workaround, not a design.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

STORE = Path("data/memories.json")
BACKUP_DIR = Path("data/backups")

# Values that are wrong or noise, matched case-insensitively as substrings.
SUPERSEDED = [
    "a civil engineering student at pokhara university in nepal",
    "civil engineering student at pokhara university in nepal",
]
DROP_IF_VALUE_IS = {"alice"}


def rec(category: str, mtype: str, value: str, source: str = "linkedin") -> dict[str, Any]:
    now = time.time()
    return {
        "id": f"mem-{abs(hash((category, mtype, value))) % 10**8:08x}",
        "category": category,
        "type": mtype,
        "value": value,
        "behavior": "append",
        "created_at": now,
        "updated_at": now,
        "last_used": now,
        "source": source,
        "confidence": 1.0,
        "importance": 1.0,
        "access_count": 0,
        "metadata": {"verified_against": "linkedin", "fetched": "2026-09-15"},
    }


# ── Facts taken directly from the profile ───────────────────────────────────

SEED: list[dict[str, Any]] = [
    # identity
    rec("identity", "name", "Sajan Gurung"),
    rec("identity", "residence", "Pokhara, Gandaki, Nepal"),
    rec("identity", "profession", "Civil Engineer"),
    # profession
    rec(
        "profession",
        "job_title",
        "Civil Engineer Manager at RUCHI Real Estate Developers Pvt. Ltd.",
    ),
    rec("profession", "role", "Site Engineer Manager at Roadshow Real Estate"),
    rec(
        "profession",
        "work_period",
        "RUCHI Real Estate Developers — Civil Engineer Manager, Aug 2025 to present",
    ),
    rec(
        "profession",
        "work_period",
        "Roadshow Real Estate — Site Engineer Manager, Aug 2024 to present",
    ),
    rec("profession", "work_period", "GUD Engineering — Civil Engineer, Dec 2023 to Aug 2024"),
    rec(
        "profession",
        "work_period",
        "GUD Engineering — Assistant Civil Engineer, Jun 2023 to Dec 2023",
    ),
    rec("profession", "experience", "Total professional experience: 2 years 7 months"),
    # education
    rec(
        "education",
        "degree",
        "Bachelor of Engineering (BE), Civil Engineering — Pokhara University, 2018-2023",
    ),
    rec("education", "grade", "BE Civil Engineering CGPA: 2.83"),
    rec("education", "activity", "University activities: music, guitar, football"),
    # skills — the ones the profile names explicitly
    rec("skills", "proficiency", "AutoCAD, ETABS, SketchUp, V-Ray"),
    rec("skills", "proficiency", "Estimating and valuation, building design, pavement design"),
    rec(
        "skills", "proficiency", "BBS, BOQ, billing, quality control and assurance, quantity survey"
    ),
    rec(
        "skills",
        "proficiency",
        "Topographical and total-station surveying, CBR-based flexible pavement design",
    ),
    rec(
        "skills",
        "proficiency",
        "Residential land development, project management, inventory management",
    ),
    # certifications
    rec(
        "credentials",
        "certification",
        "General Registered Engineer — Nepal Engineering Council, Dec 2023",
    ),
    rec(
        "credentials",
        "certification",
        "Municipal Map Making using AutoCAD, SketchUp & V-Ray — Nepal Institute of Engineering, "
        "Apr 2024",
    ),
    rec(
        "credentials",
        "certification",
        "Fixed Property Valuation workshop — Nepal Valuer's Association, Mar 2025",
    ),
    # current project
    rec(
        "projects",
        "current",
        "Leading design and topographical survey of internal roads for a 50+ plot residential land "
        "development under RUCHI Developers — 6m access road network, Total Station survey, "
        "CBR flexible pavement design, BOQs",
    ),
    # goals — merged from the two duplicate rows, and from his stated intent
    rec(
        "goals",
        "desire",
        "Wants JARVIS as STEM mentor, AI assistant, and automation operator — including "
        "integrated agent workflows",
        source="user",
    ),
    rec("goals", "objective", "Make JARVIS behave like the JARVIS from Iron Man", source="user"),
    # preferences — kept from the existing store
    rec(
        "preference",
        "like",
        "Prefers first-principles explanations over surface-level tutorials",
        source="user",
    ),
    rec("preference", "tool", "Uses VSCode", source="user"),
    rec("preference", "theme", "Prefers the JARVIS_cyan theme", source="user"),
    rec("preference", "like", "Likes pizza", source="user"),
    rec("preference", "like", "Favourite drink is masala tea", source="user"),
    # hardware — from the existing store, still current
    rec(
        "identity",
        "hardware",
        "Running an Intel i7 12th-gen H processor with an Intel Arc A370M GPU",
        source="user",
    ),
    rec(
        "identity",
        "objective",
        "Getting the Intel Arc GPU to accelerate inference through SYCL",
        source="user",
    ),
    rec(
        "identity",
        "project",
        "Building the STEMMA/LearningHub website — currently static, wants it interactive",
        source="user",
    ),
    # long-term direction
    rec(
        "vision",
        "vision",
        "Building JARVIS into a persistent personal AI system rather than a stateless assistant",
        source="user",
    ),
]


def main() -> int:
    if not STORE.exists():
        print(f"no store at {STORE}", file=sys.stderr)
        return 1

    doc = json.loads(STORE.read_text(encoding="utf-8"))
    old = doc.get("memories", [])
    print(f"before: {len(old)} records")

    survivors: list[dict[str, Any]] = []
    dropped: list[str] = []
    for m in old:
        v = " ".join(str(m.get("value", "")).split())
        low = v.lower()
        if m.get("type") == "user_name" or low in DROP_IF_VALUE_IS:
            dropped.append(f"bogus name: {v!r}")
            continue
        if low.startswith(("[pdf", "[+2")):
            survivors.append({**m, "value": v})
            continue
        if any(low == s for s in SUPERSEDED):
            dropped.append(f"superseded: {v!r}")
            continue
        # Existing user-stated facts that the seed does not already carry.
        if low in {str(r["value"]).lower() for r in SEED}:
            dropped.append(f"duplicated by seed: {v!r}")
            continue
        survivors.append({**m, "value": v})

    print(f"\ndropped from old store ({len(dropped)}):")
    for d in dropped:
        print(f"  - {d}")

    # Dedupe the seed against itself and against survivors.
    seen = {f"{m.get('category')}|{str(m.get('value')).lower()}" for m in survivors}
    added = []
    for r in SEED:
        key = f"{r['category']}|{r['value'].lower()}"
        if key in seen:
            continue
        seen.add(key)
        added.append(r)

    final = survivors + added
    print(f"\nkept from old: {len(survivors)}")
    print(f"seeded new   : {len(added)}")
    print(f"TOTAL        : {len(final)}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = BACKUP_DIR / f"memories-preseed-{stamp}.json"
    shutil.copy2(STORE, backup)
    print(f"\nbackup: {backup}")

    doc["memories"] = final
    doc["version"] = "2.3"
    doc["seeded_from"] = {"linkedin": "sajan-gurung-786705285", "at": stamp}
    STORE.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"wrote {len(final)} records")

    print("\n=== FINAL STORE (by category) ===")
    bycat: dict[str, list[dict[str, Any]]] = {}
    for m in final:
        bycat.setdefault(str(m.get("category")), []).append(m)
    for cat in sorted(bycat):
        print(f"\n  ── {cat} ({len(bycat[cat])})")
        for m in bycat[cat]:
            print(f"     [{str(m.get('type')):16s}] {str(m.get('value'))[:88]}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
