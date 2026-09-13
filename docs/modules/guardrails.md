# Tiered Safety Policy Subsystem (`app/guardrails/`) - Version-by-Version History

**Status**: ACTIVE
**Type**: reference
**Last Updated**: 2026-09-13
**Source**: `app/guardrails/` at HEAD

## Version-by-Version Evolutionary History

### Version v0.1.0 to v2.2.0 (`e13ee67` - `b2c2211`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 | Tag Release Date: 2026-06-27*
- **Unrestricted Local Execution**: Direct model calls and script execution had no authorization policy checks or safety gates.

### Version v2.3.0 (`c84d53b`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-06 | Tag Release Date: 2026-07-14*
- **Tool Registry Metadata**: Basic tool parameter schema validation inside `ToolRegistry`.

### Version v3.0.0 (`81e45f0`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 | Tag Release Date: 2026-07-26*
- **Security Hardening**: Sanitization of input file paths and system prompt parameters.

### Version v3.0.0 Refactored (`f4d5e01` - `ec0dc4e`) - Current HEAD
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 | Tag Release Date: 2026-07-26*
- **Tiered Tool Safety Policy & Decorator Gates (`app/guardrails/`)**:
  - `ToolSafetyPolicy` (`policy.py`): Central policy evaluation engine.
  - `@safety_gate` (`decorator.py`): Decorator wrapping atomic tool functions.
  - Policy Tiers:
    - `SAFE`: Read-only tools (`read_file`, `git_log`). Auto-approved.
    - `SENSITIVE`: State modifying tools (`write_file`). Verified against policy.
    - `DESTRUCTIVE`: System modifying tools (`create_directory`, file deletion, shell execution). Requires explicit Human-In-The-Loop (HITL) approval.
- **Active Invariants at HEAD**:
  1. All tool functions decorated with `@safety_gate`.
  2. Execution pauses with `AWAITING_APPROVAL` status when a `DESTRUCTIVE` step lacks client approval.
