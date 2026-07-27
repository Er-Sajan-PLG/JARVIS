#!/usr/bin/env python3
"""
scripts/update_doc_dates.py
Audits and updates exact feature author dates vs release tag dates across all docs in docs/.
"""

import os
import re

# Exact Mapping of Release Tag / Commit to Feature Author Date and Tag Release Date
COMMIT_DATES = {
    "v0.1.0": {"feature_date": "2026-06-27", "tag_date": "2026-06-27", "commit": "e13ee67"},
    "v0.2.0": {"feature_date": "2026-06-27", "tag_date": "2026-06-27", "commit": "ded44b9"},
    "v0.3.0": {"feature_date": "2026-06-27", "tag_date": "2026-06-27", "commit": "8b1d0cb"},
    "v0.4.0": {"feature_date": "2026-06-27", "tag_date": "2026-06-27", "commit": "e5c6fd6"},
    "v0.5.0": {"feature_date": "2026-06-28", "tag_date": "2026-06-28", "commit": "4034bf7"},
    "v0.7.0": {"feature_date": "2026-06-28", "tag_date": "2026-06-28", "commit": "7803a93"},
    "v0.8.0": {"feature_date": "2026-06-29", "tag_date": "2026-06-29", "commit": "d43f6e9"},
    "v1.0.0": {"feature_date": "2026-06-29", "tag_date": "2026-06-29", "commit": "6316917"},
    "v2.0.0": {"feature_date": "2026-07-03", "tag_date": "2026-07-03", "commit": "8519f65"},
    "v2.1.0": {"feature_date": "2026-07-05", "tag_date": "2026-07-05", "commit": "df45be2"},
    "v2.2.0": {"feature_date": "2026-07-05", "tag_date": "2026-07-05", "commit": "b2c2211"},
    "v2.3.0": {"feature_date": "2026-07-06", "tag_date": "2026-07-14", "commit": "c84d53b"},
    "v2.4.0": {"feature_date": "2026-07-11", "tag_date": "2026-07-14", "commit": "6ea9796"},
    "v2.4.1": {"feature_date": "2026-07-13", "tag_date": "2026-07-14", "commit": "1cab1b1"},
    "v2.4.2": {"feature_date": "2026-07-14", "tag_date": "2026-07-14", "commit": "6034224"},
    "v2.5.0": {"feature_date": "2026-07-18", "tag_date": "2026-07-18", "commit": "f9fa068"},
    "v3.0.1": {"feature_date": "2026-07-19 (RAG) / 2026-07-26 (Catalog)", "tag_date": "2026-07-26", "commit": "81e45f0"},
    "v3.0.1 Refactored": {"feature_date": "2026-07-28", "tag_date": "2026-07-28", "commit": "ec0dc4e"}
}

def fix_devlog_dates():
    devlog_path = "docs/DEVLOG.md"
    if not os.path.exists(devlog_path):
        return
    with open(devlog_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Ensure header dates include feature author date and release tag date
    replacements = [
        ("## v3.0.1 Refactored (2026-07-28)", "## v3.0.1 Refactored\n- **Feature Commit Date**: 2026-07-28 (`c5a97b4` - `ec0dc4e`)\n- **Tag Release Date**: 2026-07-28"),
        ("## v3.0.1 (2026-07-26)", "## v3.0.1\n- **Feature Commit Dates**: 2026-07-19 (RAG Subsystem `e35d468`-`ba2026f`) | 2026-07-26 (Catalog Expansion `81e45f0`)\n- **Tag Release Date**: 2026-07-26"),
        ("## v2.5.0", "## v2.5.0\n- **Feature Commit Date**: 2026-07-18 (`f9fa068`)\n- **Tag Release Date**: 2026-07-18"),
        ("## v2.4.2", "## v2.4.2\n- **Feature Commit Date**: 2026-07-14 (`6034224`)\n- **Tag Release Date**: 2026-07-14"),
        ("## v2.4.1", "## v2.4.1\n- **Feature Commit Date**: 2026-07-13 (`1cab1b1`)\n- **Tag Release Date**: 2026-07-14"),
        ("## v2.4.0", "## v2.4.0\n- **Feature Commit Date**: 2026-07-11 (`6ea9796`)\n- **Tag Release Date**: 2026-07-14"),
        ("## v2.3.0", "## v2.3.0\n- **Feature Commit Date**: 2026-07-06 (`c84d53b`)\n- **Tag Release Date**: 2026-07-14"),
        ("## v2.2.0", "## v2.2.0\n- **Feature Commit Date**: 2026-07-05 (`b2c2211`)\n- **Tag Release Date**: 2026-07-05"),
        ("## v2.1.0", "## v2.1.0\n- **Feature Commit Date**: 2026-07-04 (`5fccb37`) - 2026-07-05 (`df45be2`)\n- **Tag Release Date**: 2026-07-05"),
        ("## v2.0.0", "## v2.0.0\n- **Feature Commit Date**: 2026-07-02 (`63addf6`) - 2026-07-03 (`8519f65`)\n- **Tag Release Date**: 2026-07-03"),
        ("## v1.0.0", "## v1.0.0\n- **Feature Commit Date**: 2026-06-29 (`2922129` - `6316917`)\n- **Tag Release Date**: 2026-06-29"),
        ("## v0.8.0", "## v0.8.0\n- **Feature Commit Date**: 2026-06-29 (`d43f6e9`)\n- **Tag Release Date**: 2026-06-29"),
        ("## v0.7.0", "## v0.7.0\n- **Feature Commit Date**: 2026-06-28 (`7a840ee` - `7803a93`)\n- **Tag Release Date**: 2026-06-28"),
        ("## v0.5.0", "## v0.5.0\n- **Feature Commit Date**: 2026-06-28 (`94e1956` - `4034bf7`)\n- **Tag Release Date**: 2026-06-28"),
        ("## v0.4.0", "## v0.4.0\n- **Feature Commit Date**: 2026-06-27 (`39b3d5b` - `e5c6fd6`)\n- **Tag Release Date**: 2026-06-27"),
        ("## v0.3.0", "## v0.3.0\n- **Feature Commit Date**: 2026-06-27 (`163f8a1` - `8b1d0cb`)\n- **Tag Release Date**: 2026-06-27"),
        ("## v0.2.0", "## v0.2.0\n- **Feature Commit Date**: 2026-06-27 (`ded44b9`)\n- **Tag Release Date**: 2026-06-27"),
        ("## v0.1.0", "## v0.1.0\n- **Feature Commit Date**: 2026-06-27 (`1999e53` - `e13ee67`)\n- **Tag Release Date**: 2026-06-27")
    ]

    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)

    with open(devlog_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[+] Updated {devlog_path} with dual feature author dates and tag dates.")

def fix_changelog_dates():
    changelog_path = "docs/CHANGELOG.md"
    if not os.path.exists(changelog_path):
        return
    with open(changelog_path, "r", encoding="utf-8") as f:
        content = f.read()

    replacements = [
        ("## [v3.0.1 Refactored] - 2026-07-28", "## [v3.0.1 Refactored]\n- **Feature Author Date**: 2026-07-28 (`c5a97b4` - `ec0dc4e`)\n- **Tag Release Date**: 2026-07-28"),
        ("## [v3.0.1] - 2026-07-26 (`81e45f0`, `2c855c7`, `d23f5a0`)", "## [v3.0.1]\n- **Feature Author Dates**: 2026-07-19 (RAG Subsystem `e35d468`-`ba2026f`) | 2026-07-26 (Catalog Expansion `81e45f0`)\n- **Tag Release Date**: 2026-07-26 (`81e45f0`, `2c855c7`, `d23f5a0`)"),
        ("## [v2.5.0] - 2026-07-18 (`f9fa068`)", "## [v2.5.0]\n- **Feature Author Date**: 2026-07-18 (`f9fa068`)\n- **Tag Release Date**: 2026-07-18"),
        ("## [v2.4.2] - 2026-07-14 (`6034224`)", "## [v2.4.2]\n- **Feature Author Date**: 2026-07-14 (`6034224`)\n- **Tag Release Date**: 2026-07-14"),
        ("## [v2.4.1] - 2026-07-13 (`1cab1b1`)", "## [v2.4.1]\n- **Feature Author Date**: 2026-07-13 (`1cab1b1`)\n- **Tag Release Date**: 2026-07-14"),
        ("## [v2.4.0] - 2026-07-11 (`6ea9796`)", "## [v2.4.0]\n- **Feature Author Date**: 2026-07-11 (`6ea9796`)\n- **Tag Release Date**: 2026-07-14"),
        ("## [v2.3.0] - 2026-07-06 (`c84d53b`)", "## [v2.3.0]\n- **Feature Author Date**: 2026-07-06 (`c84d53b`)\n- **Tag Release Date**: 2026-07-14")
    ]

    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)

    with open(changelog_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[+] Updated {changelog_path} with dual feature author dates and tag dates.")

if __name__ == "__main__":
    fix_devlog_dates()
    fix_changelog_dates()
