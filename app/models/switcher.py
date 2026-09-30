# app/models/switcher.py
"""
Runtime model profile switcher.
Lets you switch between local and cloud mid-session without restarting.
"""

import re

from app.models.client import ModelClient
from app.models.factory import create_client
from app.models.omni_client import OmniModelClient
from app.models.utils import resolve_env_key
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


class ModelSwitcher:
    """
    Manages the active profile and the clients it resolves to.

    A "profile" is a name mapped to the ``ModelClient`` it selects. The switcher
    does not build ``ModelRouter`` objects: that class is an abandoned
    abstraction with **zero** ``BaseLLMProvider`` implementations in this tree,
    and its failover intent is served by ``OmniModelClient`` over the
    ``ModelClient`` protocol that actually shipped (see the note in
    ``app/adapters/http/router.py``). Earlier revisions registered into it here,
    which could not work -- ``ModelRouter`` has no ``register`` or ``set_default``
    method -- and the resulting ``AttributeError`` was swallowed by a blanket
    ``except Exception`` at construction, silently degrading the switcher to an
    empty profile. ``_routers`` therefore holds clients, not routers.

    Commands:
        model           → show current profile and active models
        model local     → switch to local profile
        model cloud     → switch to cloud profile
        model list      → list all available profiles and models
        model <name>    → switch to a named profile
    """

    def __init__(self, settings):
        # No hardcoded profiles. Build one client per configured model, group
        # them by role, and expose a single "omni" profile that fans out across
        # every role. "default" prefers a local Ollama client when present.
        self._settings = settings
        self._routers: dict[str, ModelClient] = {}
        self._clients: dict[str, ModelClient] = {}
        self._active_profile = ""

        # Pre-build clients for all configured models.
        for key, model_cfg in settings.models.items():
            try:
                self._clients[key] = create_client(model_cfg)
            except Exception as e:
                logger.warning("Could not load '%s': %s", key, e)

        # Build the "omni" profile: an OmniModelClient fanning out across the
        # clients of every role. This is the profile that actually fails over.
        role_clients: dict[str, list[ModelClient]] = {}
        for client in self._clients.values():
            try:
                role = getattr(client, "role", None) or "general"
            except Exception:
                # `role` is a property on some providers, and a raising property
                # must not take the whole switcher down. `getattr`'s default does
                # not cover this: it only handles a MISSING attribute, not one
                # whose accessor raises.
                logger.warning("Client %r raised on .role; treating as 'general'", client)
                role = "general"
            role_clients.setdefault(role, []).append(client)

        if role_clients:
            omni = OmniModelClient([c for group in role_clients.values() for c in group])
            self._routers["omni"] = omni
        else:
            logger.warning("No usable models found for the omni profile")

        default_local = self._build_default_local_router(settings)
        if default_local is not None:
            self._routers["default"] = default_local

        requested = getattr(settings, "active_profile", "")
        if requested in self._routers and self._is_usable(self._routers[requested]):
            self._active_profile = requested
        elif "default" in self._routers:
            self._active_profile = "default"
        elif "omni" in self._routers:
            self._active_profile = "omni"
        elif self._routers:
            self._active_profile = next(iter(self._routers))
        else:
            self._active_profile = ""

    def _build_default_local_router(self, settings) -> ModelClient | None:
        """The client the "default" profile should select, or None.

        Prefers the smallest local Ollama model, measured by parameter count in
        the model name, so a laptop picks the model it can actually run.
        """
        candidates = [
            key
            for key, model_cfg in settings.models.items()
            if getattr(model_cfg, "backend", "") == "ollama" and key in self._clients
        ]
        if not candidates:
            return None

        default_key = min(
            candidates,
            key=lambda key: self._ollama_model_size(settings.models[key].name),
        )
        return self._clients[default_key]

    def _ollama_model_size(self, name: str) -> float:
        if not isinstance(name, str):
            return float("inf")
        match = re.search(r"(\d+(?:\.\d+)?)(?:\s*)([kKmMgGbB])\b", name)
        if not match:
            return float("inf")
        value = float(match.group(1))
        unit = match.group(2).lower()
        if unit == "k":
            return value / 1000.0
        if unit == "m":
            return value
        if unit == "g":
            return value * 1000.0
        if unit == "b":
            return value
        return value

    def switch(self, profile: str) -> bool:
        if profile not in self._routers:
            return False
        # Reject profiles whose router has no usable model (e.g. every
        # referenced model failed to load). Otherwise route() would later
        # raise and crash the session — see docs/API.md latent risk.
        if not self._is_usable(self._routers[profile]):
            return False
        self._active_profile = profile
        return True

    @property
    def router(self) -> ModelClient:
        """The client the active profile selects.

        Named ``router`` for callers that predate this change, but it is a
        ``ModelClient``: the abandoned ``ModelRouter`` was never populated.
        """
        return self._routers[self._active_profile]

    @property
    def active_profile(self) -> str:
        return self._active_profile

    def get_client(self, key: str) -> ModelClient | None:
        return self._clients.get(key)

    def status(self) -> str:
        lines = [f"Active profile: {self._active_profile}"]
        lines.append("\nAvailable profiles:")
        for profile in self._routers:
            marker = "●" if profile == self._active_profile else "○"
            lines.append(f"  {marker} {profile}")
        lines.append("\nLoaded models:")
        for key, client in self._clients.items():
            lines.append(f"  {key}: {client.model_name} ({client.role})")
        return "\n".join(lines)

    def switch_to_model(self, model_key: str) -> bool:
        """
        Route every role to a single specific cloud/local model.
        Returns False if that model didn't load (e.g. missing API key).
        """
        client = self._clients.get(model_key)
        if not client:
            return False
        key = f"model:{model_key}"
        self._routers[key] = client
        self._active_profile = key
        return True

    def switch_to_dynamic_model(self, backend: str, model_id: str, api_key: str) -> bool:
        """Route every role to an arbitrary cloud model id, building the client on the fly.

        Lets the user pick ANY model OpenRouter/Grok/Google serves without
        pre-listing it in config.yaml — the provider routes dynamically to the
        model id we pass. ``backend`` is "openrouter"/"grok"/"google";
        ``api_key`` can be either:
          - "env:ENV_VAR_NAME" to read from environment
          - direct API key string (user-provided via headers)
        Returns False if the client can't be built (e.g. missing key).
        """
        from app.config.settings import ModelConfig

        # If it's an env reference, resolve it
        try:
            api_key = resolve_env_key(api_key)
        except ValueError as e:
            logger.warning("Dynamic model %s: %s", backend, e)
            return False

        cfg = ModelConfig(name=model_id, role="general", backend=backend, api_key=api_key)
        try:
            client = create_client(cfg)
        except Exception as e:
            logger.warning("Could not build dynamic %s client for '%s': %s", backend, model_id, e)
            return False
        key = f"dyn:{backend}:{model_id}"
        self._routers[key] = client
        self._active_profile = key
        return True

    def list_profiles(self) -> str:
        return self.status()

    @staticmethod
    def _is_usable(client: ModelClient | None) -> bool:
        """True if a profile can resolve to a client that can generate.

        This previously tested ``router.default_model``, an attribute the
        abandoned ``ModelRouter`` does not define, so it raised
        ``AttributeError`` on the real object and returned truthy only for
        ``MagicMock`` -- which is what every test supplied.
        """
        if client is None:
            return False
        return callable(getattr(client, "generate", None))
