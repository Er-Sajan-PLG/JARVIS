#!/usr/bin/env node
// Pin every third-party GitHub Action to a full commit SHA.
//
// Why this exists. `uses: actions/checkout@v7` names a *mutable tag*. Whoever can
// move that tag can run arbitrary code in this repository's CI with a token that
// can write artifacts and -- since the ci-gate workflow requests id-token: write
// for keyless provenance -- mint OIDC identities. That is the classic
// Pinned-Dependencies gap (OpenSSF Scorecard) and it was reported as SUP-010
// against 18 occurrences across .github/. The audit recommended this script by
// name, but it had never been written, so the finding had no fix to point at.
//
// A tag and a SHA differ only in mutability, so pinning is invisible to readers
// unless the human-readable version is kept beside it. The rewrite therefore
// emits `@<40-hex> # vX.Y.Z`, which also leaves Dependabot able to raise updates:
// it understands the trailing comment and rewrites both parts together.
//
// Usage:
//   node scripts/pin-actions.mjs           # rewrite in place
//   node scripts/pin-actions.mjs --check   # exit 1 if any ref is not a SHA
//
// Network: resolving a tag to a SHA needs the GitHub API. Results are cached in
// memory per run; on a rate limit the script reports which refs it could not
// resolve rather than silently leaving them unpinned.

import { readFileSync, writeFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = process.cwd();
const CHECK = process.argv.includes("--check");

// Local actions (`./.github/actions/...`) are this repository's own code and are
// already pinned by the commit that contains them.
const LOCAL = /^\.\//;

// A uses value that is already `<owner>/<repo>(/<path>)?@<40-hex>`.
const PINNED = /^([^@\s]+)@([0-9a-f]{40})(\s*#.*)?$/;
const UNPINNED = /^([^@\s]+)@(\S+)$/;

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.ya?ml$/.test(entry)) out.push(full);
  }
  return out;
}

const cache = new Map();

async function resolve(ref) {
  if (cache.has(ref)) return cache.get(ref);
  const [slug, tag] = ref.split("@");
  const url = `https://api.github.com/repos/${slug}/commits/${tag}`;
  const headers = { Accept: "application/vnd.github+json" };
  // Unauthenticated requests are rate-limited to 60/hour; a token raises that a
  // great deal and CI always has one.
  if (process.env.GITHUB_TOKEN) headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;

  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`${ref}: HTTP ${res.status} resolving ${url}`);
  }
  const body = await res.json();
  const sha = body.sha;
  if (!/^[0-9a-f]{40}$/.test(sha)) throw new Error(`${ref}: API returned a non-SHA payload`);
  cache.set(ref, sha);
  return sha;
}

async function main() {
  const files = walk(join(ROOT, ".github"));
  const unresolved = [];
  const failed = [];
  let rewritten = 0;

  for (const file of files) {
    const original = readFileSync(file, "utf8");
    const lines = original.split("\n");
    let changed = false;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const m = line.match(/^(\s*(?:-\s+)?uses:\s+)(\S+)(\s*#.*)?$/);
      if (!m) continue;
      const [, prefix, ref] = m;
      if (LOCAL.test(ref)) continue;
      if (PINNED.test(ref)) continue;

      const unpinned = ref.match(UNPINNED);
      if (!unpinned) {
        failed.push(`${relative(ROOT, file)}:${i + 1} unparseable uses value: ${ref}`);
        continue;
      }
      const [, slug, tag] = unpinned;

      if (CHECK) {
        unresolved.push(`${relative(ROOT, file)}:${i + 1} ${ref}`);
        continue;
      }

      let sha;
      try {
        sha = await resolve(ref);
      } catch (err) {
        failed.push(`${relative(ROOT, file)}:${i + 1} ${err.message}`);
        continue;
      }
      lines[i] = `${prefix}${slug}@${sha} # ${tag}`;
      changed = true;
      rewritten++;
    }

    if (changed) writeFileSync(file, lines.join("\n"), "utf8");
  }

  if (failed.length) {
    console.error("Could not resolve every action ref:");
    for (const f of failed) console.error(`  ${f}`);
    process.exit(2);
  }

  if (CHECK && unresolved.length) {
    console.error(`FAIL: ${unresolved.length} action ref(s) are not pinned to a commit SHA:`);
    for (const u of unresolved) console.error(`  ${u}`);
    console.error("\nRun `node scripts/pin-actions.mjs` to pin them.");
    process.exit(1);
  }

  if (CHECK) {
    console.log(`OK: every third-party action is pinned to a commit SHA (${files.length} files).`);
  } else {
    console.log(`Pinned ${rewritten} action ref(s) across ${files.length} workflow files.`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(2);
});
