#!/usr/bin/env python3
"""
scripts/refactor_docs_structure.py
Refactors and reorganizes docs/ into a clean, modern, zero-clutter hierarchy.
"""

import os
import shutil


def refactor_docs():
    print("[*] Starting /docs directory refactor...")

    # 1. Create metadata/ directory
    os.makedirs("docs/metadata", exist_ok=True)
    os.makedirs("docs/adr", exist_ok=True)

    # 2. Move JSON graphs to docs/metadata/
    json_files = [
        "docs/api_graph.json",
        "docs/module_graph.json",
        "docs/history_graph.json",
        "docs/knowledge_graph.json",
    ]
    for jf in json_files:
        if os.path.exists(jf):
            dest = os.path.join("docs/metadata", os.path.basename(jf))
            shutil.move(jf, dest)
            print(f"  [+] Moved {jf} -> {dest}")

    # 3. Move ADRs to lowercase docs/adr/
    if os.path.exists("docs/ADR"):
        for fname in os.listdir("docs/ADR"):
            src = os.path.join("docs/ADR", fname)
            dest = os.path.join("docs/adr", fname)
            if os.path.isfile(src):
                shutil.move(src, dest)
                print(f"  [+] Moved {src} -> {dest}")
        shutil.rmtree("docs/ADR")
        print("  [+] Removed legacy docs/ADR/ directory.")

    # 4. Clean up legacy / redundant / scratch files
    scratch_files = [
        "docs/test.md",
        "docs/project_notes.md",
        "docs/PROJECT_HISTORY.md",
        "docs/ARCHITECTURE_CONTINUE_AGENT.md",
        "docs/modules/tmp.md",
        "docs/modules/home.md",
        "docs/modules/docs.md",
        "docs/modules/app.md",
        "docs/modules/external.md",
        "docs/modules/prompts.md",
    ]
    for sf in scratch_files:
        if os.path.exists(sf):
            os.remove(sf)
            print(f"  [-] Removed redundant scratch file {sf}")

    # 5. Remove legacy debugging subfolder if redundant with DEBUGGING.md
    if os.path.exists("docs/debugging"):
        shutil.rmtree("docs/debugging")
        print("  [-] Removed legacy docs/debugging/ directory.")

    # 6. Rename/Reorganize docs/architecture/ files
    arch_renames = [
        ("docs/architecture/architecture.md", "docs/architecture/components.md"),
        ("docs/architecture/agents.md", "docs/architecture/cognitive_brain.md"),
        ("docs/architecture/models.md", "docs/architecture/model_routing.md"),
        ("docs/architecture/memory.md", "docs/architecture/memory_subsystem.md"),
        ("docs/architecture/data-flow.md", "docs/architecture/data_flow.md"),
        ("docs/architecture/startup-flow.md", "docs/architecture/startup_flow.md"),
    ]
    for old_p, new_p in arch_renames:
        if os.path.exists(old_p):
            shutil.move(old_p, new_p)
            print(f"  [+] Renamed {old_p} -> {new_p}")

    print("[+] /docs directory refactor completed successfully!")


if __name__ == "__main__":
    refactor_docs()
