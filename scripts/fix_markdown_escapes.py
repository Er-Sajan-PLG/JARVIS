#!/usr/bin/env python3
"""
scripts/fix_markdown_escapes.py
Replaces invalid '\\|' escape sequences with clean ' | ' across all markdown files.
"""

import os


def fix_markdown_escapes():
    count = 0
    for root, _, files in os.walk("."):
        if any(ignored in root for ignored in [".git", ".venv", "node_modules"]):
            continue
        for file in files:
            if file.endswith(".md"):
                filepath = os.path.join(root, file)
                with open(filepath, encoding="utf-8") as f:
                    content = f.read()
                if "\\|" in content:
                    content = content.replace("\\|", " | ")
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    count += 1
                    print(f"[+] Cleaned invalid markdown escapes in {filepath}")

    print(f"[*] Fixed markdown escapes across {count} files.")


if __name__ == "__main__":
    fix_markdown_escapes()
