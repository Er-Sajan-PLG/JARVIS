# ADR-019: Model Profiles Map to Clients; ModelRouter Is Not on the Request Path

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-09-30

- **Status**: Approved
- **Date**: 2026-09-30
- **Confidence**: `VERIFIED`

## Context

ADR-009 decided a multi-provider failover pool in which every provider
implements `BaseLLMProvider`, and `ModelRouter` routes requests away from
providers whose circuit is `OPEN`. Three of its four clauses shipped. The first
and the fourth did not:

- **Zero classes in `app/` subclass `BaseLLMProvider`.** The ABC exists in
  `app/models/interface.py`; nothing implements it.
- **`ModelRouter` can therefore never be populated.** Its public API is exactly
  `KEYWORDS`, `classify_prompt`, `generate`, `register_provider`,
  `select_healthy_provider`. The only registration path,
  `register_provider(provider)`, type-checks against `BaseLLMProvider`, so with
  no implementations it always rejects its argument.
- **Nothing calls `ModelRouter.generate` in production.**
  `app/adapters/http/router.py` already recorded this in a comment: *"The router
  is an abandoned abstraction… its failover intent is already served by
  `OmniModelClient` over the `ModelClient` protocol that actually shipped."*

The live path is different and works: `ModelSwitcher` builds a
`dict[str, ModelClient]` via `create_client`, and `get_client(key)` resolves an
entry. Failover is `OmniModelClient`, which holds a list of `ModelClient`s.
`ResourceManager`'s circuit breakers are real and are consumed there.

The two paths were mixed. `ModelSwitcher.__init__`, `switch_to_model`,
`switch_to_dynamic_model` and `model_selector._build_ollama_router` constructed a
`ModelRouter` and called `router.register(TaskType(role), client)` and
`router.set_default(client)` — **twelve call sites, none of which exist as
methods on `ModelRouter`.** Every one raised `AttributeError`.

The failure was invisible for two compounding reasons:

1. A blanket `except Exception` in `ModelSwitcher.__init__` logged
   `"Failed to build omni router"` and set `_active_profile = ""`. The switcher
   came up with **no profiles** and the application did not report an error.
2. `_is_usable` read `router.default_model`, another attribute `ModelRouter`
   does not define, so it raised too — and returned truthy only for a
   `MagicMock`, which is what every test supplied.

`test_switcher.py` patched `ModelRouter` in **33 places**. Because `MagicMock`
auto-creates any attribute, `mock.register(...)` and `mock.set_default(...)`
succeeded, and the suite asserted against an interface that has never existed.
The defect was latent rather than active only because
`_build_default_local_router` returns early on a host with no Ollama-backed
model; configure one and the `AttributeError` fires.

## Decision

**A model profile is a name mapped to a `ModelClient`. `ModelSwitcher` does not
construct `ModelRouter`.**

1. `ModelSwitcher._routers` is `dict[str, ModelClient]` — profile name to the
   client it selects. `_clients` remains the full catalog.
2. The `router` property returns the active profile's `ModelClient`, not a
   `ModelRouter`. It keeps its name for callers that predate this decision; its
   return type is documented at the property.
3. The blanket `except Exception` around profile construction is removed. A
   failure to build a profile is no longer converted into a silently empty
   switcher.
4. `_is_usable` judges a client: it must expose a callable `generate`. It no
   longer reads an attribute that does not exist.
5. `ModelClient` (`app/models/client.py`) is `@runtime_checkable`, so
   `isinstance(x, ModelClient)` is a real check. Without it, `isinstance` on a
   Protocol raises `TypeError`, and mocking the class under test was the only
   available substitute — which is precisely the coupling that hid this defect.
6. `ModelRouter` is retained as-is. It is left in the tree rather than deleted
   because ADR-009's intent is not withdrawn; it is unimplemented.
   `tests/unit/test_router_call_sites.py` guards that these modules never
   construct it again.

## Alternatives considered

- **Implement `BaseLLMProvider` and populate `ModelRouter` as ADR-009
  intended.** Rejected: it duplicates working failover. `OmniModelClient`
  already holds an ordered list of clients and iterates on failure, and is
  consumed on the live path today. Writing a second failover mechanism to
  satisfy a diagram would add a code path with no caller and a second place for
  provider health to diverge.
- **Delete `ModelRouter` outright.** Rejected as out of scope for this change.
  It is imported by `app/models/__init__.py` and covered by
  `tests/unit/test_models_router.py` and `tests/unit/test_phase2.py`, which test
  its classification and circuit-breaker behaviour directly. Those tests pass and
  describe real code; removing the class is a separate decision with its own
  migration.
- **Keep the call sites and make the mocks strict
  (`MagicMock(spec=ModelRouter)`).** Rejected: this would have converted a
  silent success into an immediate, correct failure — useful, but it fixes the
  test rather than the twelve broken production paths.
- **Wrap the calls in `hasattr` guards.** Rejected: `hasattr` returning `False`
  for every method would make the code path a no-op with extra steps, and
  preserves the illusion that `ModelRouter` participates in routing.

## Consequences

### Positive

- A user with an Ollama model configured now gets a working switcher instead of
  a silently empty one. `active_profile` resolves to `default` or `omni`.
  **Scoped honestly:** this is true of the component, not of the running
  application, because nothing in `app/` constructs `ModelSwitcher` — see
  "Reachability" below. The fix removes a trap for whoever wires it up; it does
  not change any behaviour a user can presently reach.
- `mypy --strict app/` fell **521 → 504**. The abandoned abstraction was itself
  generating type debt, because every call into it was checked against methods
  the class does not define. `.governance/mypy_baseline.txt` is lowered to lock
  the gain.
- Fixed a second latent `AttributeError` in `app/utils/model_selector.py`, which
  formatted the default profile entry as
  `default_router.default_model.model_name` — an attribute on none of
  `ModelClient`, `ModelRouter` or `OmniModelClient`. It now reads `.model_name`
  from the client.
- The model-mocking tests in `test_switcher.py` are replaced by tests that
  assert observable switcher state, so the same class of defect fails loudly.

### Negative

- `docs/architecture/model_routing.md` and `docs/ARCHITECTURE.md` drew
  `ModelRouter` on the request path. The routing doc now carries a section
  stating what actually runs; the diagrams are retained as a description of the
  circuit-breaker *mechanism*.
- ADR-009 remains `Approved` with two unimplemented clauses. It is not rewritten
  (an ADR records the decision of its date); this ADR records the divergence.
- `_routers` holding clients rather than routers is a misleading name that this
  change keeps for compatibility. Renaming it to `_profiles` is a follow-up.

## Reachability: this subsystem is not wired into the application

Verified 2026-09-30 at HEAD, after the fix. Recording it here because ADR-019
would otherwise read as though a running code path was repaired.

- **`ModelSwitcher` is constructed zero times in `app/`.** The only non-test
  constructions are `legacy/server.py:107,409` and
  `legacy/web_api_server.py:111,448`. `legacy/` is retired: `app/` does not
  import it, and `tests/sprint3/test_langgraph_engine_contract.py::test_legacy_server_import_blocked`
  asserts that importing the old `app.api.server` is blocked.
- **`_startup_model_select` (`app/utils/model_selector.py:84`) is called from
  nowhere.** Only its own definition matches in `app/`, `scripts/` and `legacy/`.
- **`app/utils/model_selector.py` references `ModelSwitcher` only in a
  docstring** (line 6). It does not import it. The two modules form a closed
  loop with no entry point.
- The live path is `app/adapters/web/router.py`, which calls
  `container.create_model_client(config)` for chat. Profile switching is not
  part of it.

So `ModelRouter`, `DocumentationAgent` (see `docs/AGENTS.md`) and this
switcher/selector pair are three components with no production call site. All
three were exercised only by direct construction in tests, and all three stayed
green while being unreachable — the switcher's tests by mocking the class under
test, the doc agent's by constructing it by hand.

**What that does and does not change about this ADR.** The decision stands: a
profile maps to a client, and `ModelRouter` must not be constructed here. That is
correct code regardless of whether it runs, and it is the precondition for wiring
the switcher up safely rather than the thing that makes it live. What it does not
support is any claim that a user-visible failure was repaired.

**Open question, not decided here:** whether to wire the switcher/selector into
the app, or delete them alongside `legacy/`. That is a product decision with a
migration, and it is deliberately not taken in this ADR.

---

## Related

- ADR-009 — Multi-Provider Failover & Circuit Breaker (the decision this
  partially supersedes in practice)
- ADR-006 — Pragmatic Hybrid Architecture
- `docs/architecture/model_routing.md` — carries the observed-status note
