# app/models/switcher.py
"""
Runtime model profile switcher.
Lets you switch between local and cloud mid-session without restarting.
"""

import re

from app.config.settings import get_settings
from app.models.client import ModelClient
from app.models.factory import create_client
from app.models.router import ModelRouter, TaskType
from app.utils.logging_setup import get_logger
from app.models.omni_client import OmniModelClient

logger = get_logger(__name__)


class ModelSwitcher:
    """
    Manages active profile and builds routers on demand.
    
    Commands:
        model           → show current profile and active models
        model local     → switch to local profile
        model cloud     → switch to cloud profile
        model list      → list all available profiles and models
        model <name>    → switch to a named profile
    """

    def __init__(self, settings):
        # New behavior: no hardcoded profiles. Build clients and create a
        # single automatic "omni" router that contains all available clients
        # grouped by role. Default active profile is "omni" and the router's
        # default model prefers a local Ollama client when present.
        self._settings = settings
        self._routers: dict[str, ModelRouter] = {}
        self._clients: dict[str, ModelClient] = {}

        # Pre-build clients for all configured models.
        for key, model_cfg in settings.models.items():
            try:
                self._clients[key] = create_client(model_cfg)
            except Exception as e:
                logger.warning("Could not load '%s': %s", key, e)

        # Build an "omni" router from all successfully created clients.
        try:
            role_clients: dict[str, list] = {}
            for key, client in self._clients.items():
                try:
                    role = getattr(client, 'role', 'general') or 'general'
                except Exception:
                    role = 'general'
                role_clients.setdefault(role, []).append(client)

            omni_router = ModelRouter()
            for role, clients in role_clients.items():
                try:
                    omni = OmniModelClient(clients)
                    omni_router.register(TaskType(role), omni)
                except Exception:
                    logger.warning("Could not register omni role %s", role)

            default_local = self._build_default_local_router(settings)
            if default_local is not None:
                self._routers['default'] = default_local
                omni_router.set_default(default_local.default_model)

            if self._is_usable(omni_router):
                self._routers['omni'] = omni_router
            else:
                logger.warning('No usable models found for omni router')

            requested = getattr(settings, 'active_profile', '')
            if requested in self._routers and self._is_usable(self._routers[requested]):
                self._active_profile = requested
            elif 'default' in self._routers:
                self._active_profile = 'default'
            elif 'omni' in self._routers:
                self._active_profile = 'omni'
            elif self._routers:
                self._active_profile = next(iter(self._routers))
            else:
                self._active_profile = ''
        except Exception:
            logger.exception('Failed to build omni router')
            self._active_profile = ''

    def _build_router(self, mapping: dict) -> ModelRouter:
        router = ModelRouter()
        for role, model_key in mapping.items():
            client = self._clients.get(model_key)
            if not client:
                continue
            try:
                task_type = TaskType(role)
                router.register(task_type, client)
            except ValueError:
                pass  # unknown role — skip

        # Set default
        default_key = mapping.get("general")
        if default_key and default_key in self._clients:
            router.set_default(self._clients[default_key])

        return router

    def _build_default_local_router(self, settings) -> ModelRouter | None:
        candidates = [
            key for key, model_cfg in settings.models.items()
            if getattr(model_cfg, 'backend', '') == 'ollama' and key in self._clients
        ]
        if not candidates:
            return None

        default_key = min(
            candidates,
            key=lambda key: self._ollama_model_size(settings.models[key].name),
        )
        client = self._clients[default_key]
        router = ModelRouter()
        for role in ["general", "code", "reasoning", "docs", "stem", "autocomplete"]:
            try:
                router.register(TaskType(role), client)
            except ValueError:
                pass
        router.set_default(client)
        return router

    def _ollama_model_size(self, name: str) -> float:
        if not isinstance(name, str):
            return float('inf')
        match = re.search(r"(\d+(?:\.\d+)?)(?:\s*)([kKmMgGbB])\b", name)
        if not match:
            return float('inf')
        value = float(match.group(1))
        unit = match.group(2).lower()
        if unit == 'k':
            return value / 1000.0
        if unit == 'm':
            return value
        if unit == 'g':
            return value * 1000.0
        if unit == 'b':
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
    def router(self) -> ModelRouter:
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
        router = ModelRouter()
        for role in ["general", "code", "reasoning", "docs", "stem", "autocomplete"]:
            try:
                router.register(TaskType(role), client)
            except ValueError:
                pass
        router.set_default(client)
        key = f"model:{model_key}"
        self._routers[key] = router
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
        import os
        from app.config.settings import ModelConfig
        
        # If it's an env reference, resolve it
        if api_key.startswith("env:"):
            env_var = api_key[4:]
            api_key = os.environ.get(env_var, "")
            if not api_key:
                logger.warning("Dynamic model %s: %s not set", backend, env_var)
                return False
        
        cfg = ModelConfig(name=model_id, role="general", backend=backend, api_key=api_key)
        try:
            client = create_client(cfg)
        except Exception as e:
            logger.warning("Could not build dynamic %s client for '%s': %s", backend, model_id, e)
            return False
        router = ModelRouter()
        for role in ["general", "code", "reasoning", "docs", "stem", "autocomplete"]:
            try:
                router.register(TaskType(role), client)
            except ValueError:
                pass
        router.set_default(client)
        key = f"dyn:{backend}:{model_id}"
        self._routers[key] = router
        self._active_profile = key
        return True

    def list_profiles(self) -> str:
        return self.status()

    @staticmethod
    def _is_usable(router) -> bool:
        """True if a router can resolve *some* model: it must have at least
        one registered task model or a configured default."""
        if router is None:
            return False
        return bool(getattr(router, "models", None)) or router.default_model is not None
