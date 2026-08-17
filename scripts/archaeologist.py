#!/usr/bin/env python3
"""
scripts/archaeologist.py
Tree-Aware Repository Archaeology Engine.
- Scans current docs/ directory tree.
- Overwrites existing doc files with real Git code history.
- Creates new docs for unmapped modules matching existing layout/frontmatter.
"""

import subprocess
import shlex
import json
import re
import os
from pathlib import Path

STATE_FILE = ".archaeology/state.json"
DOCS_DIR = "docs"

CLASS_REGEX = re.compile(r'^\+\s*(?:class|interface|type|struct)\s+([A-Za-z0-9_]+)')
FUNC_REGEX = re.compile(r'^\+\s*(?:async\s+)?(?:def|function|const|let|var)\s+([A-Za-z0-9_]+)\s*=?\s*(?:\(|\=\>)')
DEL_CLASS_REGEX = re.compile(r'^\-\s*(?:class|interface|type|struct)\s+([A-Za-z0-9_]+)')
DEL_FUNC_REGEX = re.compile(r'^\-\s*(?:async\s+)?(?:def|function|const|let|var)\s+([A-Za-z0-9_]+)\s*=?\s*(?:\(|\=\>)')

def run_git(cmd):
    res = subprocess.run(["git"] + shlex.split(cmd), capture_output=True, text=True)
    if res.returncode != 0:
        raise Exception(f"Git execution failed: git {cmd}\n{res.stderr}")
    return res.stdout.strip()

def scan_existing_docs_tree():
    """Maps all existing files in the docs/ directory."""
    existing_files = {}
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR, exist_ok=True)
        return existing_files

    for root, _, files in os.walk(DOCS_DIR):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), DOCS_DIR)
            existing_files[rel_path] = os.path.join(root, file)
            
    return existing_files

def analyze_commit_diff(commit_hash):
    """Parses exact patch deltas for symbols and modified file paths."""
    patch = run_git(f'show --patch --unified=0 {commit_hash}')
    numstat = run_git(f'show --numstat --format="" {commit_hash}')

    changed_files = []
    for line in numstat.split('\n'):
        if line.strip():
            parts = line.split('\t')
            if len(parts) == 3:
                changed_files.append({
                    "additions": parts[0],
                    "deletions": parts[1],
                    "path": parts[2]
                })

    symbols_added = []
    symbols_deleted = []
    current_file = "unknown"

    for line in patch.split('\n'):
        if line.startswith('+++ b/'):
            current_file = line[6:]
            continue

        m_class = CLASS_REGEX.search(line)
        if m_class:
            symbols_added.append({"name": m_class.group(1), "type": "class", "file": current_file})
            continue

        m_func = FUNC_REGEX.search(line)
        if m_func:
            symbols_added.append({"name": m_func.group(1), "type": "function", "file": current_file})
            continue

        m_dclass = DEL_CLASS_REGEX.search(line)
        if m_dclass:
            symbols_deleted.append({"name": m_dclass.group(1), "type": "class", "file": current_file})
            continue

        m_dfunc = DEL_FUNC_REGEX.search(line)
        if m_dfunc:
            symbols_deleted.append({"name": m_dfunc.group(1), "type": "function", "file": current_file})

    return {
        "changed_files": changed_files,
        "symbols_added": symbols_added,
        "symbols_deleted": symbols_deleted
    }

def run_archaeology():
    os.makedirs(".archaeology", exist_ok=True)
    existing_docs = scan_existing_docs_tree()
    print(f"[*] Detected {len(existing_docs)} existing files in '{DOCS_DIR}/' tree.")

    raw_commits = run_git('log --reverse --format="%H|%d|%an|%ci|%s"')
    commits = []
    for line in raw_commits.split('\n'):
        if not line.strip():
            continue
        parts = line.split('|')
        ref_names = parts[1]
        tags = []
        if 'tag:' in ref_names:
            for item in ref_names.strip(' ()').split(','):
                item = item.strip()
                if item.startswith('tag:'):
                    tags.append(item.replace('tag:', '').strip())

        commits.append({
            "hash": parts[0],
            "tags": tags,
            "author": parts[2],
            "date": parts[3],
            "subject": parts[4]
        })

    state = {
        "total_commits": len(commits),
        "history_timeline": [],
        "symbols": {},
        "modules_detected": set()
    }

    current_tag = "INITIAL"
    for idx, c in enumerate(commits, 1):
        commit_hash = c["hash"]
        if c["tags"]:
            current_tag = ", ".join(c["tags"])

        diff = analyze_commit_diff(commit_hash)

        # Track active module directories
        for f in diff["changed_files"]:
            path_parts = f["path"].split('/')
            if len(path_parts) > 1:
                state["modules_detected"].add(path_parts[0])

        state["history_timeline"].append({
            "sequence_index": idx,
            "commit": commit_hash,
            "tag": current_tag,
            "author": c["author"],
            "date": c["date"],
            "subject": c["subject"],
            "files_changed": [f["path"] for f in diff["changed_files"]]
        })

        for sym in diff["symbols_added"]:
            key = f"{sym['name']}@{sym['file']}"
            state["symbols"][key] = {
                "name": sym["name"],
                "type": sym["type"],
                "file": sym["file"],
                "birth_commit": commit_hash,
                "death_commit": None,
                "status": "ACTIVE"
            }

        for sym in diff["symbols_deleted"]:
            key = f"{sym['name']}@{sym['file']}"
            if key in state["symbols"]:
                state["symbols"][key]["death_commit"] = commit_hash
                state["symbols"][key]["status"] = "DELETED"

    # Write state
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=list)

    # 1. OVERWRITE / CREATE CORE JSON GRAPHS
    write_file(os.path.join(DOCS_DIR, "api_graph.json"), json.dumps(state["symbols"], indent=2))
    write_file(os.path.join(DOCS_DIR, "history_graph.json"), json.dumps(state["history_timeline"], indent=2))

    # 2. OVERWRITE / CREATE CORE MARKDOWN FILES
    history_md = "# Repository Archaeology: Timeline & History\n\n"
    for item in state["history_timeline"]:
        tag_str = f" `[{item['tag']}]`" if item['tag'] else ""
        history_md += f"### [{item['sequence_index']}] Commit `{item['commit'][:7]}`{tag_str} - {item['subject']}\n"
        history_md += f"**Author:** {item['author']} | **Date:** {item['date']}\n\n"
        history_md += f"**Files Modified:** {', '.join(item['files_changed'][:5])}\n\n"

    write_file(os.path.join(DOCS_DIR, "HISTORY.md"), history_md)

    lineage_md = "# Symbol Lineage & Tombstone Registry\n\n"
    lineage_md += "| Symbol Name | Type | File Path | Birth Commit | Death Commit | Status |\n"
    lineage_md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
    for key, sym in state["symbols"].items():
        death_str = f"`{sym['death_commit'][:7]}`" if sym["death_commit"] else "N/A"
        lineage_md += f"| `{sym['name']}` | {sym['type']} | `{sym['file']}` | `{sym['birth_commit'][:7]}` | {death_str} | {sym['status']} |\n"

    write_file(os.path.join(DOCS_DIR, "SYMBOL_LINEAGE.md"), lineage_md)

    # 3. OVERWRITE / CREATE MODULE DOCS MATCHING DETECTED CODE TREE
    modules_dir = os.path.join(DOCS_DIR, "modules")
    os.makedirs(modules_dir, exist_ok=True)

    for mod in state["modules_detected"]:
        mod_file = os.path.join(modules_dir, f"{mod}.md")
        
        # Filter symbols for this module
        mod_symbols = [s for k, s in state["symbols"].items() if s["file"].startswith(mod)]
        
        content = f"""---
doc_id: DOC-{mod.upper()}
title: "{mod.capitalize()} Subsystem"
target_audience: ["developers", "JARVIS"]
generated_from: "repository_archaeology"
---

# {mod.capitalize()} Subsystem

## 1. Overview
[Auto-generated from repository tree scan]

## 2. Active Symbols & API Surface
| Symbol | Type | Source File | Introduced Commit | Status |
| :--- | :--- | :--- | :--- | :--- |
"""
        for s in mod_symbols:
            content += f"| `{s['name']}` | {s['type']} | `{s['file']}` | `{s['birth_commit'][:7]}` | {s['status']} |\n"

        write_file(mod_file, content)

    print(f"\n[+] Successfully updated and synchronized files in '{DOCS_DIR}/'")

def write_file(filepath, content):
    """Overwrites existing file or creates parent dirs and file if missing."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    status = "OVERWRITTEN" if os.path.exists(filepath) else "CREATED"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [{status}] {filepath}")

if __name__ == "__main__":
    run_archaeology()