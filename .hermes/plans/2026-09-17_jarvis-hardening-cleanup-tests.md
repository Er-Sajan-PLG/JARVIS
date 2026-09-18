# JARVIS Doc Hardening, Cleanup & Test Coverage Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Harden doc-sync governance, remove dead code with proof, fix dependency issues, achieve test coverage, fix frontend-backend route mismatches, then implement missing features.

**Architecture:** Strengthen `scripts/board/review.py` with doc-drift detection, dependency cross-referencing, and dead-code detection. Clean up codebase methodically with proof for every destructive action.

**Tech Stack:** Python 3.11, FastAPI, pytest, ruff, mypy, ChromaDB

---

## Phase 1: Doc Sync Hardening

### Task 1.1: Add doc-drift detection to governance check

**Objective:** Add `doc_drift` check to `scripts/board/review.py` that fails when docs don't match code.

**Files:**
- Modify: `scripts/board/review.py`

**Step 1: Add check function**

Add to `scripts/board/review.py`:

```python
def check_doc_drift(self) -> CheckResult:
    """Verify docs match code — fail when drifted."""
    issues = []
    
    # Check API_CONTRACT.md routes match actual routes
    api_contract = Path("docs/API_CONTRACT.md").read_text()
    web_router = Path("app/adapters/web/router.py").read_text()
    
    # Extract routes from API_CONTRACT.md
    contract_routes = set(re.findall(r'(GET|POST|PUT|DELETE|PATCH)\s+(/\S+)', api_contract))
    
    # Extract actual routes from router.py
    actual_routes = set(re.findall(r'@web_router\.(get|post|put|delete|patch)\(["\'](\S+)["\']', web_router))
    actual_routes = {(m.upper(), path) for m, path in actual_routes}
    
    # Compare
    for method, path in contract_routes:
        if (method, path) not in actual_routes:
            issues.append(f"API_CONTRACT.md declares {method} {path} but router.py has no handler")
    
    for method, path in actual_routes:
        if (method, path) not in contract_routes:
            issues.append(f"router.py has {method} {path} but API_CONTRACT.md doesn't document it")
    
    # Check CAPABILITY_CONTRACT.md features have code
    cap_contract = Path("docs/CAPABILITY_CONTRACT.md").read_text()
    
    return CheckResult(
        name="doc_drift",
        passed=len(issues) == 0,
        issues=issues,
    )
```

**Step 2: Run governance check**

Run: `.venv/bin/python scripts/board/review.py`
Expected: `doc_drift` appears in results

**Step 3: Commit**

```bash
git add scripts/board/review.py
git commit -m "feat(governance): add doc_drift check to governance"
```

---

### Task 1.2: Add dependency cross-referencing to governance check

**Objective:** Add `dep_drift` check that fails when imports don't match requirements.txt or vice versa.

**Files:**
- Modify: `scripts/board/review.py`

**Step 1: Add check function**

```python
def check_dep_drift(self) -> CheckResult:
    """Verify imports match requirements.txt."""
    issues = []
    
    # Parse requirements.txt
    req_pkgs = {}
    for line in Path("requirements.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            req_pkgs[name.strip().lower()] = version.strip()
    
    # Scan all imports in app/
    imported_pkgs = set()
    for pyfile in Path("app").rglob("*.py"):
        for line in pyfile.read_text().splitlines():
            if line.startswith("import ") or line.startswith("from "):
                pkg = line.split()[1].split(".")[0]
                imported_pkgs.add(pkg)
    
    # Check: imported but not in requirements
    for pkg in imported_pkgs:
        if pkg in ("app", "os", "sys", "json", "re", "pathlib", "logging", "typing", "collections", "dataclasses", "datetime", "functools", "abc", "contextlib", "enum", "io", "uuid", "warnings", "inspect", "string", "time", "unicodedata", "hashlib", "hmm", "math", "copy", "numbers", "textwrap", "itertools", "functools"):
            continue
        if pkg not in req_pkgs:
            issues.append(f"Import '{pkg}' not found in requirements.txt")
    
    # Check: in requirements but never imported
    for pkg in req_pkgs:
        if pkg not in imported_pkgs and pkg.replace("-", "_") not in imported_pkgs:
            issues.append(f"Package '{pkg}' in requirements.txt never imported")
    
    return CheckResult(name="dep_drift", passed=len(issues)==0, issues=issues)
```

**Step 2: Run governance check**

Run: `.venv/bin/python scripts/board/review.py`
Expected: `dep_drift` appears in results

**Step 3: Commit**

```bash
git add scripts/board/review.py
git commit -m "feat(governance): add dep_drift check to governance"
```

---

### Task 1.3: Update docs to match code (API_CONTRACT.md)

**Objective:** Fix API_CONTRACT.md to reflect actual routes.

**Files:**
- Modify: `docs/API_CONTRACT.md`

**Step 1: Get actual routes**

Run: `grep -E '@(web_router|http_router)\.(get|post|put|delete|patch)\(' app/adapters/web/router.py app/adapters/http/router.py`

**Step 2: Update API_CONTRACT.md**

Add missing routes, remove non-existent ones.

**Step 3: Commit**

```bash
git add docs/API_CONTRACT.md
git commit -m "docs: sync API_CONTRACT.md with actual routes"
```

---

### Task 1.4: Add docs for undocumented code

**Objective:** Add docs for code that exists but is undocumented.

**Files:**
- Create: `docs/modules/integrations/ocr.md`
- Create: `docs/modules/integrations/agy.md`
- Create: `docs/modules/tools/workspace.md`
- Create: `docs/modules/artifacts.md`
- Create: `docs/modules/context.md`
- Create: `docs/modules/session.md`
- Create: `docs/modules/models/router.md`
- Create: `docs/modules/provider_registry.md`
- Create: `docs/modules/telemetry/index.md`
- Create: `docs/modules/memory/conversation_store.md`

**Step 1: Create each module doc**

Each doc follows template from `docs/DOC-GOVERNANCE.md §10`.

**Step 2: Run doc check**

Run: `.venv/bin/python scripts/check_docs.py`
Expected: All pass

**Step 3: Commit**

```bash
git add docs/modules/
git commit -m "docs: add module docs for undocumented code"
```

---

## Phase 2: Dead Code Removal (with proof)

### Task 2.1: Investigate `create_otlp_exporter`

**Objective:** Determine if `create_otlp_exporter` is truly dead code.

**Files:**
- Read: `app/telemetry/otel_exporter.py:131`

**Step 1: Search for usage**

Run: `grep -rn 'create_otlp_exporter' /home/sajan/Projects/JARVIS/ --include='*.py' | grep -v __pycache__`

**Step 2: If no usage found, check git history**

Run: `git log -p --all -S 'create_otlp_exporter' -- '*.py'`

**Step 3: If truly dead, remove with explanation**

```bash
git add app/telemetry/otel_exporter.py
git commit -m "refactor: remove dead code create_otlp_exporter

Function was defined but never called. Removed after git history
search confirmed no references in any branch.

Proof: `grep -rn create_otlp_exporter` returns only the definition line."
```

---

### Task 2.2: Investigate `ConversationManager`

**Objective:** Determine if `ConversationManager` class is truly dead code.

**Files:**
- Read: `app/conversation/manager.py`

**Step 1: Search for usage**

Run: `grep -rn 'ConversationManager' /home/sajan/Projects/JARVIS/ --include='*.py' | grep -v __pycache__ | grep -v 'class ConversationManager'`

**Step 2: If only referenced in docstring/comments, check if it's the same class**

The `MemoryService` has `conversation_store.py` that mentions it. Verify it's a different class.

**Step 3: If truly dead, remove with explanation**

```bash
git add app/conversation/manager.py
git commit -m "refactor: remove dead ConversationManager class

Class was defined but never instantiated. The memory store
references it only in a docstring. Removed after grep + git log
confirmed no callers.

Proof: `grep -rn ConversationManager` shows 1 class def + 1 docstring only."
```

---

### Task 2.3: Investigate other potential dead code

**Objective:** Check remaining items from gap analysis.

**Files:**
- Search: `grep -rn '^def \|^class ' app/ --include='*.py' | grep -v __pycache__`

**Step 1: For each definition, search for usage (excluding definition line)**

Run: `for name in <names>; do echo "=== $name ==="; grep -rn "$name" app/ --include='*.py' | grep -v __pycache__ | grep -v "^.*:class $name\|^.*:def $name"; done`

**Step 2: Remove only if zero external references**

**Step 3: Commit each removal separately with proof**

---

## Phase 3: Dependency Cleanup

### Task 3.1: Add missing `structlog` to requirements.txt

**Objective:** Add `structlog` since it's imported in 3 OCR files.

**Files:**
- Modify: `requirements.txt`

**Step 1: Add structlog**

Add `structlog>=24.0.0` to requirements.txt

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "fix(deps): add missing structlog dependency"
```

---

### Task 3.2: Remove unused dependencies (with proof)

**Objective:** Remove packages from requirements.txt that are never imported.

**Files:**
- Modify: `requirements.txt`

**Step 1: For each package in requirements.txt, grep for import**

Run: `for pkg in <package_list>; do echo "=== $pkg ==="; grep -rn "import ${pkg%%-*}\|from ${pkg%%-*}" /home/sajan/Projects/JARVIS/app/ --include='*.py' | head -3; done`

**Step 2: If no import found, check if it's a transitive dependency**

Run: `pip show <package> | grep -i "required-by"`

**Step 3: Remove only if zero imports AND not a transitive dep**

```bash
git add requirements.txt
git commit -m "chore(deps): remove unused packages

Removed packages never imported in app/:
- aiohttp, bcrypt, boolean.py, build, click, coverage, etc.

Proof: grep -rn 'import <pkg>' returned no matches for each."
```

---

## Phase 4: Test Coverage

### Task 4.1: Add tests for `app/integrations/ocr/`

**Objective:** Cover OCR backends, service, config, model_manager.

**Files:**
- Create: `tests/unit/ocr/__init__.py`
- Create: `tests/unit/ocr/test_service.py`
- Create: `tests/unit/ocr/test_unlimited_ocr.py`
- Create: `tests/unit/ocr/test_paddle_ocr.py`

**Step 1: Write failing tests**

**Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/unit/ocr/ -v`
Expected: FAIL

**Step 3: If code is correct, tests should pass after writing**

**Step 4: Commit**

```bash
git add tests/unit/ocr/
git commit -m "test(ocr): add test coverage for OCR integration"
```

---

### Task 4.2: Add tests for `app/adapters/integrations/agy.py`

**Objective:** Cover AGY CLI integration.

**Files:**
- Create: `tests/unit/integrations/test_agy.py`

**Step 1: Write tests mocking subprocess**

**Step 2: Run tests**

Run: `.venv/bin/pytest tests/unit/integrations/test_agy.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/unit/integrations/test_agy.py
git commit -m "test(integrations): add AGY CLI integration tests"
```

---

### Task 4.3: Add tests for `app/tools/workspace_tools.py`

**Objective:** Cover workspace tools.

**Files:**
- Create: `tests/unit/tools/test_workspace_tools.py`

**Step 1: Write tests**

**Step 2: Run tests**

Run: `.venv/bin/pytest tests/unit/tools/test_workspace_tools.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/unit/tools/test_workspace_tools.py
git commit -m "test(tools): add workspace tools tests"
```

---

### Task 4.4: Add tests for `app/artifacts/`

**Objective:** Cover artifact manager.

**Files:**
- Create: `tests/unit/test_artifacts.py`

**Step 1: Write tests**

**Step 2: Run tests**

**Step 3: Commit**

---

### Task 4.5: Add tests for `app/context/`

**Objective:** Cover context builder.

**Files:**
- Create: `tests/unit/test_context.py`

**Step 1: Write tests**

**Step 2: Run tests**

**Step 3: Commit**

---

### Task 4.6: Add tests for `app/session/`

**Objective:** Cover session manager, checkpointer.

**Files:**
- Create: `tests/unit/test_session.py`

**Step 1: Write tests**

**Step 2: Run tests**

**Step 3: Commit**

---

### Task 4.7: Add tests for `app/models/router.py`

**Objective:** Cover ModelRouter.

**Files:**
- Create: `tests/unit/models/test_router.py`

**Step 1: Write tests with mocked providers**

**Step 2: Run tests**

**Step 3: Commit**

---

### Task 4.8: Add tests for `app/provider_registry.py`

**Objective:** Cover ProviderRegistry.

**Files:**
- Create: `tests/unit/test_provider_registry.py`

**Step 1: Write tests**

**Step 2: Run tests**

**Step 3: Commit**

---

### Task 4.9: Add tests for `app/telemetry/`

**Objective:** Cover Tracer, OTLPExporter, MetricsCollector.

**Files:**
- Create: `tests/unit/telemetry/__init__.py`
- Create: `tests/unit/telemetry/test_tracer.py`
- Create: `tests/unit/telemetry/test_otel_exporter.py`

**Step 1: Write tests**

**Step 2: Run tests**

**Step 3: Commit**

---

### Task 4.10: Enforce coverage threshold in CI

**Objective:** Set coverage floor at 80% in CI workflow.

**Files:**
- Modify: `.github/workflows/ci.yml`

**Step 1: Update pytest command**

Change to: `.venv/bin/pytest tests/ -v --cov=app --cov-fail-under=80 --cov-report=term-missing`

**Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: enforce 80% coverage threshold"
```

---

## Phase 5: Frontend-Backend Route Fixes

### Task 5.1: Add missing POST /api/conversations route

**Objective:** Frontend calls POST /api/conversations to create/list conversations.

**Files:**
- Modify: `app/adapters/web/router.py`

**Step 1: Add route**

```python
@web_router.post("/conversations")
async def create_conversation(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a new conversation session."""
    container = bootstrap_system()
    session_id = payload.get("session_id") or str(uuid.uuid4())
    # ... create and return conversation
```

**Step 2: Add GET /api/conversations (list all)**

```python
@web_router.get("/conversations")
async def list_conversations() -> list[dict[str, Any]]:
    """List all conversations."""
    container = bootstrap_system()
    # ... return list
```

**Step 3: Commit**

---

### Task 5.2: Add POST /api/stop route

**Objective:** Frontend calls POST /api/stop to stop generation.

**Files:**
- Modify: `app/adapters/web/router.py`

**Step 1: Add route**

```python
@web_router.post("/stop")
async def stop_generation() -> dict[str, Any]:
    """Stop current generation."""
    # ... signal stop
```

**Step 2: Commit**

---

### Task 5.3: Add POST /api/conversations/{id}/pin route

**Objective:** Frontend calls this to pin messages.

**Files:**
- Modify: `app/adapters/web/router.py`

**Step 1: Add route**

```python
@web_router.post("/conversations/{session_id}/pin")
async def pin_message(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Pin a message in conversation."""
    # ... pin logic
```

**Step 2: Commit**

---

### Task 5.4: Fix /api/memories vs /api/memory mismatch

**Objective:** Frontend calls /api/memories but backend may use /api/memory.

**Files:**
- Modify: `app/adapters/web/router.py` or frontend

**Step 1: Check actual backend route**

Run: `grep -rn 'memory' app/adapters/web/router.py`

**Step 2: Add alias or fix frontend**

**Step 3: Commit**

---

### Task 5.5: Add /api/ocr/* routes

**Objective:** OCR integration exists but has no HTTP routes.

**Files:**
- Modify: `app/adapters/web/router.py` or create `app/adapters/web/ocr_routes.py`

**Step 1: Add OCR routes**

```python
@web_router.post("/ocr")
async def ocr_image(file: UploadFile = File(...)) -> dict[str, Any]:
    """Extract text from uploaded image."""
    # ... call OCR service
```

**Step 2: Commit**

---

## Phase 6: Governance Hardening

### Task 6.1: Add doc_drift and dep_drift to CI gate

**Objective:** Make new checks block CI when they fail.

**Files:**
- Modify: `scripts/board/review.py`
- Modify: `.github/workflows/ci.yml`

**Step 1: Ensure both checks run in ci_gate**

**Step 2: Make CI fail on new checks**

**Step 3: Commit**

```bash
git add scripts/board/review.py .github/workflows/ci.yml
git commit -m "ci: enforce doc_drift and dep_drift in CI gate"
```

---

## Verification

After all phases complete:

```bash
# 1. All governance checks pass
.venv/bin/python scripts/board/review.py
Expected: ✅ All checks pass (including doc_drift, dep_drift)

# 2. Coverage meets threshold
.venv/bin/pytest tests/ -v --cov=app --cov-fail-under=80
Expected: 80%+ coverage

# 3. No dead code remains
grep -rn "TODO\|FIXME\|HACK" app/ --include="*.py"
Expected: None

# 4. Dependencies clean
grep -rn "^import\|^from" app/ --include='*.py' | wc -l
# Compare with requirements.txt packages

# 5. Frontend-backend routes match
grep -E '@web_router\.' app/adapters/web/router.py | wc -l
grep -E 'api\(' frontend/js/ --include='*.js' -r | wc -l
# Should be close (not exact due to dynamic routes)
```

---

## Risks

- Removing dead code may break things if code is called via reflection/string names
- Coverage threshold may need tuning if codebase has many untestable paths
- Doc drift check may be too strict initially — may need whitelist for known drift

## Open Questions

- Should we keep `ConversationManager` for future use or remove entirely?
- Coverage threshold — 80% too aggressive for current state?
- Should dead code removal be one commit per item or batched?
