# Branch Protection Setup - Manual Configuration Required

**Limitation**: GitHub Free private repositories cannot configure branch protection with required status checks via API (requires GitHub Pro or public repository).

## Manual Configuration via GitHub UI

Go to: **Settings → Branches → Add branch protection rule**

### Branch Protection Rule for `main`

| Setting | Value |
|---------|-------|
| Branch name pattern | `main` |
| ✅ Require a pull request before merging | Enabled |
| ✅ Require approvals | 1 (or 0 for solo repo) |
| ✅ Dismiss stale PR approvals when new commits are pushed | Enabled |
| ✅ Require review from Code Owners | Enabled |
| ✅ Require status checks to pass before merging | Enabled |
| ✅ Require branches to be up to date before merging | Enabled |
| Required status checks | `Lint & Typecheck`, `Tests`, `Security Scan`, `Build`, `Conventional Commits`, `Virtual Board Governance` |
| ✅ Require conversation resolution before merging | Enabled |
| ✅ Require linear history | Enabled |
| ✅ Do not allow force pushes | Enabled |
| ✅ Do not allow bypassing the above settings | Enabled |

### After CI Runs Once

The required status checks will only appear in the dropdown **after the CI workflow has run at least once**. 

**Workflow**:
1. Push a commit to trigger CI
2. Wait for all 6 jobs to complete (Lint & Typecheck, Tests, Security Scan, Build, Conventional Commits, Virtual Board Governance)
3. Go to branch protection settings
4. Add each of the 6 checks as required status checks
5. Enable "Require branches to be up to date before merging"

### Auto-Merge Configuration

After branch protection is set up:

1. Go to **Settings → General → Pull Requests**
2. ✅ Allow auto-merge
3. ✅ Allow squash merging
4. ✅ Delete branch on merge

### Dependabot Auto-Merge

The `.github/dependabot.yml` is configured with `automerge` label. To enable:
1. Go to **Settings → Security & analysis → Dependabot alerts/updates**
2. Enable both
3. Dependabot PRs will auto-merge when CI passes (configured in `.github/dependabot.yml`)

### CODEOWNERS

`.github/CODEOWNERS` is configured - Code Owners will be automatically requested for review.

---

## Alternative: Make Repo Public (If Acceptable)

If acceptable, making the repository public enables full branch protection API access:

```bash
gh repo edit Er-Sajan-PLG/JARVIS --visibility public
# Then run: GITHUB_TOKEN=$(gh auth token) python scripts/setup_branch_protection.py
```