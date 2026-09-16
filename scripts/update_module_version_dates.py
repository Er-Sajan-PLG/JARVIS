#!/usr/bin/env python3
"""
scripts/update_module_version_dates.py
Enriches all documentation in docs/modules/*.md with exact Feature Author Dates and Tag Release Dates.
"""

import os
import re

VERSION_DATE_MAP = {
    "v0.1.0": "Feature Author Date: 2026-06-27 | Tag Release Date: 2026-06-27",
    "v0.2.0": "Feature Author Date: 2026-06-27 | Tag Release Date: 2026-06-27",
    "v0.3.0": "Feature Author Date: 2026-06-27 | Tag Release Date: 2026-06-27",
    "v0.4.0": "Feature Author Date: 2026-06-27 | Tag Release Date: 2026-06-27",
    "v0.5.0": "Feature Author Date: 2026-06-28 | Tag Release Date: 2026-06-28",
    "v0.7.0": "Feature Author Date: 2026-06-28 | Tag Release Date: 2026-06-28",
    "v0.8.0": "Feature Author Date: 2026-06-29 | Tag Release Date: 2026-06-29",
    "v1.0.0": "Feature Author Date: 2026-06-29 | Tag Release Date: 2026-06-29",
    "v2.0.0": "Feature Author Date: 2026-07-03 | Tag Release Date: 2026-07-03",
    "v2.1.0": "Feature Author Date: 2026-07-05 | Tag Release Date: 2026-07-05",
    "v2.2.0": "Feature Author Date: 2026-07-05 | Tag Release Date: 2026-07-05",
    "v2.3.0": "Feature Author Date: 2026-07-06 | Tag Release Date: 2026-07-14",
    "v2.4.0": "Feature Author Date: 2026-07-11 | Tag Release Date: 2026-07-14",
    "v2.4.1": "Feature Author Date: 2026-07-13 | Tag Release Date: 2026-07-14",
    "v2.4.2": "Feature Author Date: 2026-07-14 | Tag Release Date: 2026-07-14",
    "v2.5.0": "Feature Author Date: 2026-07-18 | Tag Release Date: 2026-07-18",
    "v3.0.1": "Feature Author Date: 2026-07-19 / 2026-07-26 | Tag Release Date: 2026-07-26",
    "v3.0.1 Refactored": "Feature Author Date: 2026-07-28 | Tag Release Date: 2026-07-28",
}


def process_modules():
    modules_dir = "docs/modules"
    if not os.path.exists(modules_dir):
        return

    for fname in os.listdir(modules_dir):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(modules_dir, fname)
        with open(fpath, encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            new_lines.append(line)
            # Match heading like ### Version v2.3.0 (`c84d53b`)
            m = re.search(r"### (?:Version|Release) (v\d+\.\d+\.\d+[\s\w]*)", line)
            if m:
                v_key = m.group(1).strip()
                for key in VERSION_DATE_MAP:
                    if key in v_key:
                        date_str = VERSION_DATE_MAP[key]
                        new_lines.append(f"- **Timeline Metadata**: *{date_str}*\n")
                        break

        with open(fpath, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        print(f"[+] Processed dates in {fpath}")


if __name__ == "__main__":
    process_modules()
