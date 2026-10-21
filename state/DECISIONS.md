# MACP DECISIONS — JARVIS

Architecture Decision Records made **under this protocol**. The repository's own
canonical ADR set lives in `docs/adr/` (19 records) and is the authority for
architectural choices — this file records coordination decisions and pointers,
not replacements.

Read this before making a design choice. Someone may have already decided it.

---

## ADR-001 — One gate definition, two runners

**Date**: 2026-10-01
**Status**: Accepted
**Supersedes**: the six-job `.github/workflows/ci.yml` (deleted)

### Context

Green meant two different things. `.github/workflows/ci.yml` published six jobs;
`scripts/ci_gate.py` published 29 checks. They had drifted:

- `bandit ... || true` and `pip-audit ... || true` — **always pass**
- `mypy` — `continue-on-error: true`, never blocking
- coverage was line-only, unaware of `--cov-branch`

The repository also became public, making Actions and branch protection usable
for the first time (both had returned HTTP 403 while private).

### Decision

GitHub Actions runs `scripts/ci_gate.py` — the same script a developer runs —
via `.github/workflows/ci-gate.yml`, as the **single** required status check
`ci-gate`.

### Consequences

**Positive**
- One definition of green; the runners cannot drift.
- The required check enforces 29 checks, not 6, and none of them is `|| true`.
- A local failure reproduces in CI and vice versa.

**Negative**
- A PR run takes ~10–15 min instead of the old few seconds (free: public repo).
- The workflow needs 12 external scanners installed on the runner.
- Two external tools (`docker`, `cosign`) make the runner heavier than a pure
  Python job.

### Alternatives rejected

- **Re-enable `ci.yml` as required.** Rejected: it would have enforced the
  *weaker* set. That is worse than enforcing nothing, because it looks enforced.
- **Keep both, require both.** Rejected: reproduces the divergence problem and
  doubles the surface for "which green counts".

---

## ADR-002 — A missing blocking scanner fails the gate

**Date**: 2026-10-01
**Status**: Accepted

### Context

`_missing_tool()` returns `status="skip"`. `Check.failed` is
`status in ("fail", "error")`, and `blocking_failures` filters on `failed`.
Therefore a gate declared `blocking=True` contributed **nothing** to
`blocking_failures` when its scanner was absent: the run concluded `success`
while the check made no claim.

Locally that is the right behaviour — a dev machine may legitimately lack `syft`.
In CI it is the most dangerous possible failure, because a green required check is
indistinguishable from a real pass.

### Decision

Add `--require-tools`. Under it, a missing **blocking** tool is a failure; a
missing non-blocking tool stays a skip. Default remains `False` so local runs are
unchanged.

`scripts/install_ci_tools.sh` fails first and more legibly, naming what is absent.

### Consequences

**Positive**
- The required check cannot go green on a partial tool install.
- The flag is explicit: a reader can see the gate is running in strict mode.

**Negative**
- A CI environment that cannot install a scanner now blocks every PR. This is
  intended: it is a signal that CI is broken, and it should be loud.

---

## ADR-003 — Provenance is keyless in CI

**Date**: 2026-10-01
**Status**: Accepted

### Context

RISK-009: `gate_provenance` signed with a local cosign keypair in
`~/.local/share/jarvis-ci-tools`, reaching SLSA L1 only — no Rekor transparency
log, no keyless OIDC. A runner cannot hold the developer's key, and pasting it
into a repo secret would put a long-lived signing key next to a public repo.

### Decision

Add `--keyless`. Cosign exchanges the job's OIDC token for a Fulcio certificate
and writes a Rekor entry. Verification pins `--certificate-identity` and
`--certificate-oidc-issuer` to this repository's own workflow.

The local keyed path is retained unchanged.

### Consequences

**Positive**
- CI-verified builds reach SLSA L2/L3 with a publicly auditable record.
- No long-lived signing key exists to leak.
- The signature binds to *this repo's workflow*, not "some Fulcio certificate" —
  any GitHub workflow in any repo can obtain one, so pinning the identity is what
  makes the provenance mean anything.

**Negative**
- RISK-009 is **narrowed, not closed**: the local path still reaches L1 only.
- Keyless signing depends on `id-token: write`; removing that permission silently
  degrades provenance back to a skip.

---

## ADR-004 — Actions are pinned by SHA, and the gate enforces it

**Date**: 2026-10-01
**Status**: Accepted

### Context

`uses: actions/checkout@v7` names a mutable tag. Whoever can move it runs
arbitrary code in this repository's CI — which now requests `id-token: write`
for keyless provenance, so that code could mint OIDC identities. Reported by the
repo's own audit as SUP-010 across 18 occurrences. The audit recommended
`scripts/pin-actions.mjs` by name; **that script had never been written**, so the
finding had no fix.

### Decision

- Write `scripts/pin-actions.mjs` (pin + `--check`).
- Pin every third-party action to a 40-hex SHA with the version in a trailing
  comment, so Dependabot can still raise updates.
- Add `gate_action_pinning` as a **blocking** gate check, written in pure Python
  rather than shelling out to node — a check that disappears with its toolchain
  is not a check.

### Consequences

**Positive**
- The SUP-010 finding has an enforced fix, not a one-time cleanup.
- A new workflow added with `@v7` fails the gate immediately.

**Negative**
- Updating an action requires Dependabot or re-running the script; a human cannot
  bump a tag by hand without also changing the digest.

---

## ADR-005 — Claim files before editing; document in-flight state honestly

**Date**: 2026-10-01
**Status**: Accepted

### Context

The bootstrap was requested while a branch carried 27 modified files. The
protocol's startup step says the working tree should be clean.

### Decision

Do **not** revert or stash the in-flight work to satisfy the checklist. Bootstrap
with the tree as-is and record the exact state in `DASHBOARD.md` §5 and the
session file. A clean-looking tree that hides real work is a worse handoff than
an honest dirty one.

### Consequences

**Positive**
- The next agent sees the true state; nothing is silently lost.

**Negative**
- The bootstrap commit and the CI/CD commit are temporarily interleaved on one
  branch. They are committed separately, in that order, to keep the history legible.

---

## ADR-007 — The signature stage verifies only the commits a push introduces

**Date**: 2026-10-21
**Author**: HERM (session `20261021-0430-HERM`)
**Status**: Accepted

### Context

`githooks/pre-push` Stage 1 required a verifiable signature on every commit in
the range it gates. For an existing branch that range is `remote_sha..local_sha`,
so as soon as a PR branch merged `main` into itself, every commit `main` had
gained since the branch was cut entered the range — including GitHub's own.

GitHub signs the commits *it* creates (Dependabot bumps, squash-merges through
the API) with GitHub's **PGP** key. This repository signs with `gpg.format=ssh`
and verifies against `gpg.ssh.allowedsignersfile`, so it holds no PGP keyring
able to check those signatures. `%G?` therefore answers `E` — *cannot check* —
not the `G`/`U` the hook requires:

```
git log -1 --format='%G?' 0349071   ->  G   (an SSH-signed commit of ours)
git log -1 --format='%G?' 4cf9f5a   ->  E   (a GitHub PGP-signed Dependabot commit)
```

The hook reported that as *"commit … is not signed"*. That message is wrong: the
commit is signed, in a format the local check cannot read. The consequence was
not a warning but a dead end — the branch could not be merged forward (push
refused) and could not be rebased into a linear shape either, because Stage 0b
refuses the force-push that would have done it. Two branches had to be rebuilt
from scratch during this session (#168 -> #179, and #167 would have hit the same
wall).

### Decision

Stage 1 gates `rev-list <range> --not --remotes=origin`. A commit already
published on the remote is not re-verified. The check applies to the commits a
push actually introduces.

The reasoning is that re-verifying a published commit cannot prevent anything: it
is already on the remote, and the remote accepted it when it landed — either
carrying a signature this same rule required, or created by GitHub itself, which
the ruleset accepts.

### Consequences

**Positive**
- A PR branch that merges `main` is pushable again, so a conflicted branch has a
  forward path that is not "rebuild it from scratch".
- The check is scoped rather than weakened: every commit the push introduces is
  still verified exactly as before.
- No third-party key material enters the trust store.

**Negative**
- A commit reachable from *any* `origin/*` remote-tracking ref is now trusted, not
  only those on `origin/main`. This is deliberate — "already published" is the
  property that matters, not which branch published it — but it does mean a commit
  pushed to a throwaway branch on origin is not re-verified on a later push.
- The exclusion depends on remote-tracking refs being present. A stale or absent
  `refs/remotes/origin/*` makes the filter match nothing, so more commits are
  checked than necessary. That direction fails closed, which is the right one.

### Rejected alternatives

| Alternative | Why not |
|---|---|
| Accept `%G? = E` outright | `E` means *cannot check*, which is exactly what a genuinely unverifiable local commit also returns. Trusting it would disable the check rather than scope it. |
| Install GitHub's PGP public key in a local keyring | Puts a third party's key into the trust store of a repository whose entire purpose is verifiable provenance. The owner rejected this explicitly. |
| Rebase every PR branch and never merge `main` | Treats the symptom. The hook would still refuse the push for anyone who did merge, and there is no way to know that without reading this record. |

### Verification

`tests/unit/test_prepush_verifies_only_new_commits.py` asserts both directions
against a real repository built to the shape that broke: a branch whose remote tip
predates a `main` that advanced, then merged. It asserts the published commit is
excluded **and** that the new commit is not — the second is the negative control,
because a change that merely stopped the hook complaining would be
indistinguishable from deleting the check. Mutation-verified: reverting the hook
change fails the test; restoring it passes.
