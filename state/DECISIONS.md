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
