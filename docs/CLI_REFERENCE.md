# CLI Reference (generated)

**Status**: ACTIVE
**Type**: reference
**Last Updated**: see git log (regenerated from source)
**Source**: `scripts/*.py` argparse declarations at HEAD

<!-- generated:cli_reference begin -->

_Regenerated from `argparse` declarations in `scripts/*.py`. Run `<script> --help` for full details._

## `scripts/check_docs.py`

| Flags | Help |
|---|---|
| `--strict` | exit non-zero when findings exist |

## `scripts/check_links.py`

| Flags | Help |
|---|---|
| `--json` | machine-readable output |
| `--table` | write a markdown table of dead links |
| `--offline` | extract links, make no requests |

## `scripts/ci_bridge.py`

| Flags | Help |
|---|---|
| `--check-auth` | — |
| `--list-prs` | — |
| `--once` | gate every open PR that still needs it |
| `--pr` | gate only this PR number |
| `--limit` | max PRs to consider (default 10) |
| `--dry-run` | run gates but publish nothing |
| `--force` | re-gate even if the SHA was already gated |
| `--json` | — |

## `scripts/ci_gate.py`

| Flags | Help |
|---|---|
| `--sha` | commit SHA to verify |
| `--base` | base ref for the ruff ratchet (default origin/main) |
| `--json` | emit machine JSON on stdout |
| `--out` | also write the JSON report to this path |
| `--keep-worktree` | — |
| `--with-coverage` | add the (non-blocking) coverage gate |
| `--with-docker` | add the (non-blocking) docker-build gate |
| `--with-mutation` | add the (non-blocking, slow) mutation gate |
| `--with-evals` | add the eval suite gate |
| `--init-signing` | create the local cosign keypair |

## `scripts/deliver_brief.py`

| Flags | Help |
|---|---|
| `--channel` | — |

## `scripts/doc_governance.py`

| Flags | Help |
|---|---|
| `--sync` | rewrite marker values from repo |
| `--check` | fail on stale markers |
| `--facts` | print current facts as JSON |
| `--run-tests` | compute test facts by running them |

## `scripts/doc_review_due.py`

| Flags | Help |
|---|---|
| `--json` | — |
| `--packet` | — |
| `--due-only` | — |

## `scripts/doc_type_table.py`

| Flags | Help |
|---|---|
| `--check` | — |
| `--write` | — |

## `scripts/github_app_token.py`

| Flags | Help |
|---|---|
| `--check` | report config + validity |
| `--installation-id` | — |
| `--print-token` | print the token (only for a manual one-off curl; it is a secret) |
| `--force-refresh` | — |

## `scripts/memory_health.py`

| Flags | Help |
|---|---|
| `--strict` | exit 1 on degradation |

## `scripts/migrate_memory_temporal.py`

| Flags | Help |
|---|---|
| `--apply` | write the migration (default: dry run) |

## `scripts/new_doc.py`

| Flags | Help |
|---|---|
| `type` | document type (see --list-types) |
| `path` | target path, e.g. docs/architecture/queue.md |
| `--title` | — |
| `--source` | the code this document describes |
| `--generated-by` | generator script, for type=generated |
| `--list-types` | — |
| `--template` | print a template to stdout |

## `scripts/publish_release.py`

| Flags | Help |
|---|---|
| `--tag` | publish a release for this tag only |
| `--backfill` | publish every tag missing a release |
| `--dry-run` | — |

## `scripts/remediate_memory_store.py`

| Flags | Help |
|---|---|
| `--apply` | write changes |
| `--store` | — |

## `scripts/run_evals.py`

| Flags | Help |
|---|---|
| `--json` | output JSON instead of terminal |
| `--suite` | suite name |
| `--package` | package to scan for evals |

## `scripts/scheduled_doc_maintenance.py`

| Flags | Help |
|---|---|
| `--check-only` | dry run, do not open issues |

## `scripts/sync_doc_facts.py`

| Flags | Help |
|---|---|
| `--apply` | rewrite marker values from the repo |
| `--check` | fail on stale markers/bare claims |
| `--sync` | compute facts once, apply to docs, verify, and write cache (one pytest run) |
| `--run-tests` | compute test facts by running them |
| `--facts-json` | use the provided JSON fact snapshot instead of computing (for CI reuse) |

## `scripts/verify_git_safety.py`

| Flags | Help |
|---|---|
| `--check` | Check a command string for forbidden patterns |

<!-- generated:cli_reference end -->
