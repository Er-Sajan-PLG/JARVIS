# app/guardrails

<!-- generated:module_readmes begin -->

| Module | Purpose | Top-level API |
|---|---|---|
| `__init__.py` | JARVIS Guardrails Package. | — |
| `approvals.py` | Human-in-the-Loop (HITL) Approval Registry. | `ApprovalAlreadyDecidedError`, `ApprovalNotFoundError`, `ApprovalRegistry`, `PendingApproval`, `_iso()`, `_parse_dt()`, `_plan_from_dict()`, `_plan_to_dict()` |
| `decorator.py` | Safety Gate Decorator for Tool Execution. | `safety_gate()`, `set_global_policy()` |
| `policy.py` | Tiered Tool Safety Policy & Approval Rules. | `HITLRequiredError`, `PolicyViolationError`, `ToolSafetyPolicy` |

<!-- generated:module_readmes end -->
