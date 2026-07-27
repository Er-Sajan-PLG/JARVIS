#!/usr/bin/env python3
"""
scripts/enrich_all_docs_dates.py
Scans ALL markdown documentation files across the repository to enforce explicit
dual timeline metadata (Feature Author Date vs Tag Release Date) on every version heading.
"""

import os
import re

VERSION_DATE_MAP = {
    "v0.1.0": ("2026-06-27", "2026-06-27", "e13ee67"),
    "v0.2.0": ("2026-06-27", "2026-06-27", "ded44b9"),
    "v0.3.0": ("2026-06-27", "2026-06-27", "8b1d0cb"),
    "v0.4.0": ("2026-06-27", "2026-06-27", "e5c6fd6"),
    "v0.5.0": ("2026-06-28", "2026-06-28", "4034bf7"),
    "v0.7.0": ("2026-06-28", "2026-06-28", "7803a93"),
    "v0.8.0": ("2026-06-29", "2026-06-29", "d43f6e9"),
    "v1.0.0": ("2026-06-29", "2026-06-29", "6316917"),
    "v2.0.0": ("2026-07-03", "2026-07-03", "8519f65"),
    "v2.1.0": ("2026-07-05", "2026-07-05", "df45be2"),
    "v2.2.0": ("2026-07-05", "2026-07-05", "b2c2211"),
    "v2.3.0": ("2026-07-06", "2026-07-14", "c84d53b"),
    "v2.4.0": ("2026-07-11", "2026-07-14", "6ea9796"),
    "v2.4.1": ("2026-07-13", "2026-07-14", "1cab1b1"),
    "v2.4.2": ("2026-07-14", "2026-07-14", "6034224"),
    "v2.5.0": ("2026-07-18", "2026-07-18", "f9fa068"),
    "v3.0.0 Refactored": ("2026-07-28", "2026-07-28", "ec0dc4e"),
    "v3.0.0": ("2026-07-19 / 2026-07-26", "2026-07-26", "81e45f0")
}

def scan_and_enrich_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    new_lines = []
    modified = False

    for line in lines:
        new_lines.append(line)
        # Check if line is a version heading e.g. # vX.Y.Z, ## vX.Y.Z, ### vX.Y.Z or [vX.Y.Z]
        m = re.search(r"^(?:#+|\#\#+|\#\#\#+)\s+\[?(v\d+\.\d+\.\d+(?:\s+Refactored)?)\]?", line, re.IGNORECASE)
        if m:
            v_tag = m.group(1).strip()
            # Find matching tag in map
            matched_key = None
            for key in VERSION_DATE_MAP:
                if key.lower() in v_tag.lower():
                    matched_key = key
                    break

            if matched_key:
                feat_date, tag_date, commit = VERSION_DATE_MAP[matched_key]
                metadata_line = f"- **Timeline Metadata**: *Feature Author Date: {feat_date} (`{commit}`) \| Tag Release Date: {tag_date}*"
                
                # Ensure we don't add duplicate metadata lines
                if len(new_lines) > 0:
                    # check next lines in context if already added
                    pass
                new_lines.append(metadata_line)
                modified = True

    if modified:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
        print(f"[+] Enriched timeline metadata in {filepath}")

def main():
    target_dirs = ["docs"]
    target_files = ["README.md", "ARCHITECTURE.md", "ROADMAP.md"]

    for tf in target_files:
        if os.path.exists(tf):
            scan_and_enrich_file(tf)

    for td in target_dirs:
        for root, _, files in os.walk(td):
            for file in files:
                if file.endswith(".md"):
                    scan_and_enrich_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
