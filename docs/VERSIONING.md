# JARVIS Versioning

How the version number is produced, and why it is built this way.

## Source of truth: git tags

**The version number comes from git tags, not from a file.** There is no
`VERSION` constant that has to be hand-edited; the running app *derives* its
version from the tag history at import time.

The scheme is `vMAJOR.MINOR.PATCH`:

| segment | meaning |
|---|---|
| MAJOR | breaking / large architectural change |
| MINOR | new capability, backwards compatible |
| PATCH | bug fix or small change |

The implementation is `app/config/version.py`. It runs
`git describe --tags --long` and produces:

| repository state | version string |
|---|---|
| HEAD exactly on a clean `vA.B.C` tag | `vA.B.C` |
| N commits ahead of the nearest tag | `vA.B.C+dev.N` |
| working tree dirty | `... .dirty` |

Example, as of this writing: HEAD is 136 commits past the `v3.0.1` tag, so the
app reports `v3.0.1+dev.136`.

Fallbacks, in order, only when git is truly absent:

1. `JARVIS_VERSION` environment variable.
2. `_FALLBACK_VERSION` in `app/config/version.py` (last known release) — used
   only for built artifacts shipped without a `.git` directory.

## Why tags and not a file

During early development the history is noisy: many commits, few stable
releases. Tagging liberally was intended to *show* development without
re-writing history (no rebasing a large repo), and to let the version follow
the tag automatically. The `+dev.N` suffix is exactly that mechanism: it tells
you "N commits past the last tagged milestone."

Once the project stabilises, the tagged milestones themselves carry the version
and the `+dev.N` suffix becomes the exception rather than the rule. The design
does not change — only the frequency of tagging does.

## One version, consumed everywhere

`app/config/version.py` is imported by:

- `app/__init__.py` → `app.__version__`
- `app/main.py` → the FastAPI `version` field (shown in `/docs` and OpenAPI)
- `app/adapters/http/router.py` → the `/health` response `version` field

All of them report the *same* git-derived string. There is deliberately no
second source of truth to drift.

## What `scripts/bump_version.py` does

`bump_version.py [patch|minor|major]` is a **convenience**, not the authority:

1. bumps the `project.version` line in `pyproject.toml` (metadata courtesy),
2. commits that change,
3. creates the `vX.Y.Z` tag — which is what actually moves the version.

It tries an annotated+signed tag (`-s`) first, and falls back to an unsigned
annotated tag when no GPG key is present, because the tag is what matters, not
the signature.

## What must NOT happen (regressions to watch for)

- **Do not hardcode a version string in the API layer.** The correct pattern
  is `from app.config.version import VERSION as __version__`; a bare
  `version="3.0.0"` is a bug — it is how the `/health` endpoint silently
  reported `3.0.0` while the app knew `v3.0.1+dev.136`.
- **Do not treat `pyproject.toml` as the version.** It is metadata; the tag is
  the number. `package.json` under the frontend is likewise not authoritative.
- **Do not edit `app/config/version.py` to change the number.** It has no
  number to edit; the number lives in the tags.

## History

- The early `v0.x`–`v2.5.0` tags (all dated 2026-07-14) are intentional
  development staging markers, not releases. They are retained as-is; the
  history is not being rewritten.
- `v3.0.0` (2026-07-26) and `v3.0.1` (2026-07-28) are the first stable tags.
- The API hardcoded `version="3.0.0"` until 2026-09-11, when it was wired to
  the git-derived `VERSION` (the defect described above).
