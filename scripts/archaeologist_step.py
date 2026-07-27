#!/usr/bin/env python3
"""
scripts/archaeologist_step.py
Version-Window Archaeology Driver for Antigravity IDE.
- Accumulates intermediate commits into .archaeology/version_buffer.json
- Signals when a version tag boundary requires merging across ALL docs/
"""

import subprocess
import json
import os
import sys

STATE_FILE = ".archaeology/state.json"
PAYLOAD_FILE = ".archaeology/current_commit.json"
BUFFER_FILE = ".archaeology/version_buffer.json"

def run_git(cmd):
    full_cmd = cmd if cmd.strip().startswith("git ") else f"git {cmd}"
    res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        raise Exception(f"Git failed: {full_cmd}\n{res.stderr}")
    return res.stdout.strip()

def get_commits():
    raw = run_git('log --reverse --format="%H|%d|%an|%ci|%s"')
    commits = []
    for line in raw.split('\n'):
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
    return commits

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def prepare_current():
    commits = get_commits()
    state = load_json(STATE_FILE, {"current_index": 0, "active_tag": "v0.0.0-draft"})
    buffer = load_json(BUFFER_FILE, [])

    idx = state["current_index"]

    if idx >= len(commits):
        res = {"status": "COMPLETE", "total_commits": len(commits)}
        print(json.dumps(res, indent=2))
        return res

    c = commits[idx]
    commit_hash = c["hash"]
    is_tag_boundary = len(c["tags"]) > 0
    tag_name = c["tags"][0] if is_tag_boundary else state["active_tag"]

    patch = run_git(f'show --patch --stat {commit_hash}')
    numstat = run_git(f'show --numstat --format="" {commit_hash}')

    commit_data = {
        "step": idx + 1,
        "commit_hash": commit_hash,
        "short_hash": commit_hash[:7],
        "author": c["author"],
        "date": c["date"],
        "subject": c["subject"],
        "tags": c["tags"],
        "is_tag_boundary": is_tag_boundary,
        "changed_files_summary": numstat,
        "patch": patch[:10000]
    }

    # Append to version buffer
    buffer.append(commit_data)
    save_json(BUFFER_FILE, buffer)

    payload = {
        "status": "IN_PROGRESS",
        "current_commit": commit_data,
        "version_tag": tag_name,
        "is_tag_boundary": is_tag_boundary,
        "buffered_commits_count": len(buffer),
        "version_buffer": buffer
    }

    save_json(PAYLOAD_FILE, payload)

    print(json.dumps({
        "status": "READY",
        "step": payload["current_commit"]["step"],
        "total": len(commits),
        "commit": payload["current_commit"]["short_hash"],
        "subject": payload["current_commit"]["subject"],
        "is_tag_boundary": is_tag_boundary,
        "tag": tag_name,
        "buffered_commits": len(buffer)
    }, indent=2))

def advance():
    state = load_json(STATE_FILE, {"current_index": 0, "active_tag": "v0.0.0-draft"})
    commits = get_commits()
    
    # If the commit was a tag boundary, update active tag and clear buffer
    c = commits[state["current_index"]]
    if c["tags"]:
        state["active_tag"] = c["tags"][0]
        save_json(BUFFER_FILE, [])  # Clear buffer after tag finalization

    state["current_index"] += 1
    save_json(STATE_FILE, state)

    if state["current_index"] >= len(commits):
        print(json.dumps({"status": "COMPLETE"}))
    else:
        prepare_current()

def reset():
    save_json(STATE_FILE, {"current_index": 0, "active_tag": "v0.0.0-draft"})
    save_json(BUFFER_FILE, [])
    print(json.dumps({"status": "RESET"}))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "current"
    if cmd == "current":
        prepare_current()
    elif cmd == "next":
        advance()
    elif cmd == "reset":
        reset()