# JARVIS Versioning

**Status**: ACTIVE
**Type**: reference
**Last Updated**: 2026-09-18
**Reviewed**: 2026-09-18
**Source**: `app/config/version.py`, `scripts/version_bump.py`

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

Example, as of 2026-09-18: HEAD sits exactly on the `v3.23.0` tag, so the app
reports `v3.23.0` with no `+dev.N` suffix.

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

## What actually cuts a release tag

**Automatic (the normal path).** `githooks/pre-push` runs on every push to the
default branch. If commits exist since the latest `vA.B.C` tag, it calls
`scripts/version_bump.py --apply --tag-only`, which:

1. computes the bump from the conventional-commit types since that tag
   (breaking → MAJOR, `feat` → MINOR, anything else → PATCH),
2. creates the annotated `vX.Y.Z` tag at HEAD,
3. pushes the tag, then publishes the matching GitHub Release
   (`scripts/publish_release.py`) — because a tag is not a release.

If there are **no** conventional commits since the last tag it refuses to bump,
rather than minting an empty patch tag. A bump failure never blocks the push; it
warns and continues.

> **Ordering trap (fixed 2026-09-13):** the hook originally published the release
> *before* pushing the tag, and `gh` refuses to release a tag the remote does not
> have yet. The tag is now pushed first. Pushing a tag re-enters the hook with
> `local_ref=refs/tags/…`, which the branch guard skips, so there is no recursion.
>
> Tags still need to be pushed explicitly if you are not going through the hook:
> `git push origin --tags`.

**Manual (rare).** `scripts/bump_version.py [patch|minor|major]` bumps the
`project.version` line in `pyproject.toml`, commits it, and creates the tag. It is
a **convenience for the metadata**, not the authority — two scripts exist and
`version_bump.py` is the one wired into the hook. It tries an annotated+signed
tag (`-s`) first and falls back to an unsigned annotated tag when no GPG key is
present, because the tag is what matters, not the signature.

> **Precedence, resolved 2026-09-18** (both scripts read end-to-end):
> **`scripts/version_bump.py` wins.** `githooks/pre-push` invokes
> `scripts/version_bump.py --apply --tag-only` on every push; nothing in the
> hook path calls `scripts/bump_version.py`. The latter only bumps the
> `pyproject.toml` metadata by hand (and installs the hooks via
> `install-hooks`); its number is never consumed by the app, which derives the
> version from tags via `app/config/version.py`.

## What must NOT happen (regressions to watch for)

- **Do not hardcode a version string in the API layer.** The correct pattern
  is `from app.config.version import VERSION as __version__`; a bare
  `version="3.0.0"` is a bug — it is how the `/health` endpoint silently
  reported `3.0.0` while the app knew `v3.0.1+dev.136` (fixed 2026-09-11).
- **Do not treat `pyproject.toml` as the version.** It is metadata; the tag is
  the number. `package.json` under the frontend is likewise not authoritative.
- **Do not edit `app/config/version.py` to change the number.** It has no
  number to edit; the number lives in the tags.

## History

- The early `v0.x`–`v2.5.0` tags (all dated 2026-07-14) are intentional
  development staging markers, not releases. They are retained as-is; the
  history is not being rewritten.
- `v3.0.0` (2026-07-26) and `v3.0.1` (2026-07-28) are the first stable tags.
- **Every `v3.1.0`+ tag was cut automatically** by the push hook described above,
  starting 2026-09-13. The current line is `v3.23.x`.
- The API hardcoded `version="3.0.0"` until 2026-09-11, when it was wired to
  the git-derived `VERSION` (the defect described above).
- `app/config/version.py`'s `_FALLBACK_VERSION` is `v3.0.1` — it is only read when
  git is unavailable, and is deliberately *not* bumped on every release.
- `mobile/package.json` (`jarvis-mobile`) and `tgcall/package.json` (`tgcall`)
  each carry an independent `"version": "1.0.0"` for their own packaging (the
  Capacitor APK wrapper and the Node sidecar). They are **not** git-derived and
  are **not** the app version — bump them only when that packaging changes.
