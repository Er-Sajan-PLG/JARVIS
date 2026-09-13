#!/usr/bin/env python3
r"""Link, anchor, heading-number and index checks for the documentation tree.

Split out of ``check_docs.py`` because these checks share a markdown parser (heading
slugs) that the path rule does not need, and because they are the checks most likely
to grow.

The anchor check exists because it is a real bug magnet that a naive path check
misses entirely. ``check_docs.py`` verifies that a backticked path resolves; it says
nothing about ``[the runner](ARCHITECTURE.md#cognitive-engine-loop)``, where the file
exists but the heading was renamed. A dead anchor is invisible to both a human
skimming the diff and a path check — and the reader who clicks it is the one who
pays.

The slug algorithm mirrors GitHub's: lowercase, strip formatting and punctuation,
spaces to hyphens. It is deliberately a *simulation*: an anchor that GitHub would
resolve but this rejects is a false positive, so the rules stay conservative
(``\w``, spaces and hyphens survive; everything else goes).
"""

from __future__ import annotations

import re
from pathlib import Path

LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

#: Targets that are deliberately not resolved here.
SKIP_PREFIXES = ("http://", "https://", "mailto:", "ftp://")


def _slug(heading: str) -> str:
    """GitHub-flavoured heading slug."""
    s = heading.strip()
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)  # [text](url) -> text
    s = s.replace("`", "").replace("*", "").replace("~", "")
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    return re.sub(r"\s+", "-", s.strip()).lower()


def headings_and_anchors(text: str) -> tuple[list[str], set[str]]:
    """Return (heading titles, anchor slugs) for a document, skipping fenced code."""
    titles: list[str] = []
    anchors: set[str] = set()
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m:
            title = m.group(2)
            titles.append(m.group(1) + " " + title)
            anchors.add(_slug(title))
    return titles, anchors


def _strip_fences(text: str) -> str:
    """Blank out fenced code blocks, preserving line count.

    A ``[x](y)`` inside a code block is an example, not a link — the same reason
    ``sync_doc_facts`` treats fences as illustrative.
    """
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def check_links(
    rel: Path, text: str, repo_root: Path, anchor_cache: dict[str, set[str]]
) -> list[str]:
    """Every markdown link must resolve to a file that exists, and to a real anchor."""
    findings: list[str] = []
    prose = _strip_fences(text)

    for m in LINK_RE.finditer(prose):
        raw = m.group("target")
        if raw.startswith(SKIP_PREFIXES):
            continue
        line_no = prose[: m.start()].count("\n") + 1

        # An absolute path or a `~/` link breaks for every reader but its author,
        # and this repo has lived at more than one path (docs/README.md §guidelines).
        if raw.startswith(("/", "~")):
            findings.append(
                f"{rel}:{line_no}: absolute link {raw!r} — use a repo-relative link "
                f"(the repo has lived at more than one path)"
            )
            continue

        path_part, _, anchor = raw.partition("#")

        if not path_part:
            # Same-file anchor: resolve against this document.
            anchors = anchor_cache.setdefault(str(rel), headings_and_anchors(text)[1])
            if anchor and anchor not in anchors:
                findings.append(
                    f"{rel}:{line_no}: dead same-file anchor #{anchor} — no heading in "
                    f"this document slugs to it"
                )
            continue

        # Resolve relative to docs/ first, then the repo root. Documents cite both.
        candidates = [repo_root / rel.parent / path_part, repo_root / path_part]
        target = next((c for c in candidates if c.exists()), None)
        if target is None:
            findings.append(f"{rel}:{line_no}: link target does not exist: {raw}")
            continue

        if anchor and target.suffix == ".md":
            key = str(target.relative_to(repo_root))
            if key not in anchor_cache:
                try:
                    anchor_cache[key] = headings_and_anchors(
                        target.read_text(encoding="utf-8", errors="replace")
                    )[1]
                except OSError:  # pragma: no cover - unreadable target
                    continue
            if anchor not in anchor_cache[key]:
                findings.append(
                    f"{rel}:{line_no}: dead anchor {raw} — {key} has no heading slugging "
                    f"to #{anchor}"
                )
    return findings


def check_heading_numbers(rel: Path, text: str) -> list[str]:
    """Catch two headings claiming the same number.

    Manual renumbering is how a document ends up with two "## 14" sections and a
    reader who cannot cite either reliably.
    """
    seen: dict[str, int] = {}
    findings: list[str] = []
    in_fence = False
    for i, line in enumerate(_strip_fences(text).splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if not m:
            continue
        num = re.match(r"^(\d+(?:\.\d+)*)\.?\s", m.group(2))
        if not num:
            continue
        key = num.group(1)
        if key in seen:
            findings.append(
                f"{rel}:{i}: heading number '{key}' already used at line {seen[key]} — "
                f"duplicate section numbers make citations ambiguous"
            )
        else:
            seen[key] = i
    return findings


def check_index_coverage(rel: Path, text: str, repo_root: Path) -> list[str]:
    """docs/README.md is the only map, so every document must be reachable from it.

    A document nobody links to is a document nobody finds — which is how the
    previous pass accumulated stubs that were already dead when they were found.

    "Reachable" means linked directly **or** linked via a directory the index
    points at. A subfolder index that names its contents in a table (e.g.
    ``[`modules/`](modules/) | Per-subsystem guides: domain, brain, …``) has made
    those documents findable; demanding one row per file would turn the map into a
    second copy of the tree, which is exactly the drift §4 rule 1 exists to prevent.
    """
    if str(rel) != "docs/README.md":
        return []
    prose = _strip_fences(text)
    linked_files: set[str] = set()
    linked_dirs: set[str] = set()
    for m in LINK_RE.finditer(prose):
        target = m.group("target").partition("#")[0]
        if not target or target.startswith(SKIP_PREFIXES):
            continue
        try:
            resolved = (repo_root / "docs" / target).resolve()
            r = str(resolved.relative_to(repo_root.resolve()))
        except ValueError:
            continue
        if resolved.is_dir():
            linked_dirs.add(r.rstrip("/") + "/")
        else:
            linked_files.add(r)

    unlinked: list[str] = []
    for p in sorted((repo_root / "docs").rglob("*.md")):
        doc_rel = str(p.relative_to(repo_root))
        if doc_rel == "docs/README.md":
            continue
        if doc_rel.startswith(("docs/archive/", "docs/adr/")):
            continue  # archived history and ADRs are indexed by their own index
        if doc_rel in linked_files:
            continue
        parent = str(p.parent.relative_to(repo_root)).rstrip("/") + "/"
        if parent in linked_dirs:
            continue  # reachable through its directory's index row
        unlinked.append(doc_rel)

    if unlinked:
        return [
            f"{rel}: {len(unlinked)} document(s) not reachable from the index — "
            f"docs/README.md is the only map, so an unlinked doc is an unfindable one: "
            + ", ".join(unlinked[:8])
            + (" …" if len(unlinked) > 8 else "")
        ]
    return []
