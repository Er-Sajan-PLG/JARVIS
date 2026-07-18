# app/models/switcher.py
"""
Runtime model profile switcher.
Lets you switch between local and cloud mid-session without restarting.
"""

from app.config.settings import get_settings
from app.models.client import ModelClient
from app.models.factory import create_client
from app.models.router import ModelRouter, TaskType
from app.utils.logging_setup import get_logger

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
        self._settings = settings
        self._active_profile = settings.active_profile
        self._routers: dict[str, ModelRouter] = {}
        self._clients: dict[str, ModelClient] = {}

        # Pre-build clients for all configured models
        for key, model_cfg in settings.models.items():
            try:
                self._clients[key] = create_client(model_cfg)
            except Exception as e:
                logger.warning("Could not load '%s': %s", key, e)

        # Build routers for each profile
        for profile_name, mapping in settings.profiles.items():
            self._routers[profile_name] = self._build_router(mapping)

        # Don't start on a dead profile: if the configured active profile's
        # router has no usable model, fall back to the first one that does.
        if not self._is_usable(self._routers.get(self._active_profile)):
            usable = next(
                (p for p, r in self._routers.items() if self._is_usable(r)),
                None,
            )
            if usable is not None:
                self._active_profile = usable

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

    def switch_to_dynamic_model(self, backend: str, model_id: str, api_key_env: str) -> bool:
        """Route every role to an arbitrary cloud model id, building the client on the fly.

        Lets the user pick ANY model OpenRouter/Grok/Google serves without
        pre-listing it in config.yaml — the provider routes dynamically to the
        model id we pass. ``backend`` is "openrouter"/"grok"/"google";
        ``api_key_env`` names the key env var (e.g. "OPENROUTER_API_KEY").
        Returns False if the client can't be built (e.g. missing key).
        """
        import os
        from app.config.settings import ModelConfig
        cfg = ModelConfig(name=model_id, role="general", backend=backend, api_key=f"env:{api_key_env}")
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
