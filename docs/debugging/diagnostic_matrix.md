# Error Symptom Diagnostic Matrix

| Error Symptom | Root Cause | Verifying Test / Commit Fix | Resolution / Remediation |
| :--- | :--- | :--- | :--- |
| `HTTP 401 Unauthorized` | Missing or invalid `JARVIS_API_KEY` in request headers | `app/adapters/http/router.py` (`ec0dc4e`) | Pass `Authorization: Bearer $JARVIS_API_KEY` header |
| `Circuit breaker OPENED for provider 'groq'` | Provider returned 429 rate limit or 503 service unavailable | `tests/unit/test_phase2.py` (`bb7e20b`) | ModelRouter automatically fails over to healthy fallback provider; circuit probes recovery after 30s |
| `HITLRequiredError: HITL approval required for destructive tool` | Executing `DESTRUCTIVE` tool (`create_directory`, file delete) without explicit approval | `tests/unit/test_phase4.py` (`f4d5e01`) | Client UI must send explicit step approval boolean `hitl_approvals={step_id: True}` |
| `Corrupt memories.json file` | Truncated or malformed JSON data on disk | `tests/unit/test_issue6.py` (`c5a97b4`) | MemoryStore automatically quarantines corrupt file to `.corrupt-*.bak` and starts clean store |
