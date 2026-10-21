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

## ADR-006 — Split the gate into one job per context, keep ONE required check

**Date**: 2026-10-21
**Author**: HERM (session `20261021-0430-HERM`)
**Status**: Accepted

### Context

`ci-gate.yml` ran all 29 gates in a single job, and that job was the single
required check. Correct, but three costs became visible:

- **Opaque failures.** A red check said only "ci-gate failed". Which of 29 gates
  failed, and whether it was blocking or reported-only, required opening a log.
- **Serial execution.** One job runs 29 gates end to end (~11 min). Most of that
  is the test suite; the scanners queued behind it.
- **Over-broad privilege.** `id-token: write` sat at workflow level, so *every*
  step — including third-party scanners — could mint an OIDC identity.

The obvious fix is more jobs. The obvious fix is also the trap this repository
already documented: the previous `setup_branch_protection.py` required six
contexts from a workflow that had never run, which would have made `main`
permanently unmergeable. And the six-job `ci.yml` that was deleted for being
*weaker* than the local gate shows the other direction of the same risk.

### Decision

Add `--context <name>` to `scripts/ci_gate.py`, selecting the checks that already
declare that context, and run one job per context. Keep exactly **one required
check** — `ci-gate`, now an aggregator that `needs:` every job and carries
`if: always()`.

The load-bearing rules:

1. The per-context jobs have **no `needs:`**. A job with `needs:` is skipped when
   its dependency fails, and a skipped job's check is never reported. Only the
   aggregator depends on others, and it is the only required context.
2. `--context` is validated against `GATE_CONTEXTS`. A typo must fail loudly; a
   context selecting nothing would report green while checking nothing.
3. The contexts must **partition** the default gate set — asserted by
   `tests/unit/test_gate_context_split.py`, not by review.

### Consequences

**Positive**
- A failure names its domain in the checks list; no log spelunking.
- Jobs run in parallel; wall-clock is the slowest context, not the sum.
- `id-token: write` is scoped to the Supply Chain job alone.
- The Tests job is a py3.11/3.12/3.13 matrix, which the single job could not be.
- One definition of green is preserved: every job is the same script, and the
  partition test makes divergence a test failure rather than a slow drift.

**Negative**
- Every job runs `install_ci_tools.sh`, so scanners are installed eight times.
  Parallel execution absorbs the wall-clock cost; it is duplicated compute.
- Eight jobs cost more Actions minutes. Free on a public repository; this would
  need revisiting if the repository became private again.
- More YAML to keep correct, and the `needs:`/`if: always()` rules above are the
  kind of thing that is easy to reintroduce wrongly. They are stated in the
  workflow header, in `AGENTS.md` §4.3, and here.

### Rejected alternatives

- **Register the per-context jobs as required checks as well.** Safe *only*
  because they have no `needs:`, but each additional required context is another
  way to deadlock the branch. The aggregator already gates on all of them.
- **Keep one job and just improve its output.** Solves the opacity, not the
  serial execution or the OIDC scope.
- **Reinstate a second workflow with its own gate logic.** This is precisely the
  two-definitions-of-green failure `ci.yml` was deleted for.
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

---

## ADR-008 — Only the default branch writes a fact marker line

**Date**: 2026-10-21
**Author**: HERM (session `20261021-0430-HERM`; design and implementation begun by a
delegated worker that died on an upstream 429 and was finished and verified here)
**Status**: Accepted

### Context

A fact marker value is a **function of the working tree** — `test_count` is the
number of tests *here*, `adr_count` the number of ADRs *here*. The pre-commit hook
ran `sync_doc_facts.py --apply/--sync` on **every** commit, so every branch
rewrote the marker lines to its own values. The default branch advances on its
own and rewrites the same lines. Both sides therefore changed the same lines, and
git reported a conflict — **structurally**, not occasionally:

- every PR that adds or removes a test,
- every dependency PR (the count moves when a package is added or dropped),
- every ADR (`adr_count`),
- and `docs/FINAL_STATE.md` / `docs/GOVERNANCE.md` on **every** merge.

Measured in one session: PR #180 went `DIRTY` for this reason alone and had to be
rebuilt; #182 went `DIRTY` on `docs/GOVERNANCE.md` for the same reason while its
own content was unrelated.

The markers themselves are not the problem — they are what makes a stale number a
gate failure instead of a silent lie (ADR-014). The problem is **who writes them**.

### Decision

**A branch must never modify a fact marker line. Only the default branch may.**

Enforced at three points, all resolving the scope through one shared function
(`doc_facts.resolve_fact_scope`), so the hook, the gate and the checkers cannot
disagree about what "the base branch's values" means:

1. **`githooks/pre-commit`** writes nothing on a non-default branch. It checks the
   marker lines against the base (blocking) and reports values stale relative to
   this tree (advisory — on a branch that is the expected state, because the
   markers describe the *published* repository, not the proposal). On the default
   branch it syncs, verifies and re-stages exactly as before.
2. **`gate_doc_facts`** scopes its check: on the default branch the markers must
   match reality (unchanged — the honesty property ADR-014 exists to protect); on
   any other branch they must equal the **base branch's** values. The base is the
   **merge base**, not the base tip, so a branch that is merely behind is not
   treated as divergent — only a change relative to the fork point can conflict.
3. **`.github/workflows/doc-facts-refresh.yml`** is the sanctioned writer on the
   default branch, and the only caller of `DOC_FACTS_REFRESH=1`. Main is
   protected and `bypass_actors` is empty, so it opens a PR rather than pushing.

The scope is also **pinned into every subprocess** the gate runs
(`DOC_FACTS_SCOPE`, `DOC_FACTS_BASE_REF`): the gate's worktree is detached and its
`--git-common-dir` HEAD belongs to the primary checkout, so a worktree that
re-derived the scope could reach the opposite conclusion. Pinning makes them
agree by construction, and `DOC_FACTS_SCOPE=default` is passed explicitly on the
default branch so a stricter scope can never be silently downgraded.

### Consequences

**Positive**

- The conflict becomes impossible **by construction** rather than by resolution:
  if a branch never touches those lines, merging the default branch's change to
  them is a clean one-sided change.
- It is also the **correct semantics**. The documents describe the published
  repository; a branch's test count is not a fact about the project, it is a fact
  about an unmerged proposal.
- The published documents stay honest: the default branch is still required to be
  accurate, and the refresh path exists to make that true.
- One definition of the scope, so a future checker cannot quietly disagree.

**Negative**

- Between a merge that moves a count and the refresh PR landing, the published
  documents are briefly stale. This is a real window, not a theoretical one.
- A contributor who edits a marker line by hand is now refused rather than
  silently corrected, which is a worse first experience and a better outcome.
- The refresh path is a second workflow to maintain, and it depends on the
  repository's auto-merge behaviour to land without a human.

### Rejected alternatives

- **A `.gitattributes` merge driver (`merge=ours` or a custom driver).** Rejected:
  a driver runs **client-side**. GitHub computes mergeability itself and does not
  run `.gitattributes` drivers, so it cannot fix the thing that was actually
  broken — the PR showing as `DIRTY`. It would also have hidden the conflict
  locally while leaving it on the server, which is worse than the problem.
- **`merge=union`.** Rejected: for a changed line it emits **both** versions, so
  the document would carry two contradictory values.
- **Deleting the markers, or reverting to prose numbers.** Rejected: that is
  ADR-014's entire point. The alternative is documents asserting numbers that
  silently drift, which is the defect ADR-014 was written to end.
- **Accepting the conflict and resolving it by hand each time.** Rejected: it
  recurred on every test-adding PR, dependency PR and ADR, and each resolution
  risked taking the wrong side — a manual step that is wrong once is worse than
  no step at all.
- **Making the markers branch-relative everywhere.** Rejected: it is the current
  behaviour and it is the cause.

### Verification

- `tests/unit/test_fact_marker_merge_conflicts.py` builds the shape that broke — a
  branch that rewrites a marker, a base that rewrites the same marker to a
  different value, then a real `git merge` — and asserts the merge is clean.
- `tests/unit/test_doc_facts.py::test_real_repository_has_no_doc_drift` is
  scope-aware: on the default branch it verifies the markers against reality; on a
  branch it verifies this tree left every base marker line unchanged, and asserts
  that it compared a non-zero number of markers so it cannot pass by measuring
  nothing. Forcing `DOC_FACTS_SCOPE=default` on a branch makes it fail with the
  old drift message, which shows the two invariants are genuinely distinct.
- `sync_doc_facts.py --check-vs-base <ref>` reports the markers compared as well as
  the findings, because a check that compared nothing must never be reported as a
  pass.
