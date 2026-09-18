"""Composition Root for Dependency Injection & Service Wiring.

Instantiates, configures, and wires all JARVIS application services, subsystems,
and event listeners.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from app.artifacts import ArtifactManager
from app.brain import ExecutionRunner, IntentAnalyzer, ResponseSynthesizer, TaskPlanner
from app.context import ContextBuilder
from app.events import InMemoryAsyncBus
from app.guardrails import ApprovalRegistry, ToolSafetyPolicy, set_global_policy
from app.memory import MemoryService
from app.models import ModelRouter
from app.prompt import PromptLoader
from app.resources import ResourceManager
from app.session import SessionManager, SessionPersistence
from app.session.checkpointer import MemorySaverAdapter, get_postgres_checkpointer
from app.telemetry import EventLogger, MetricsCollector, Tracer
from app.tools import DEFAULT_TOOLSET
from app.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


@dataclass
class ApplicationContainer:
    """Dependency Injection container holding singletons for all active subsystems."""

    event_bus: InMemoryAsyncBus
    telemetry_logger: EventLogger
    tracer: Tracer
    metrics: MetricsCollector
    prompt_loader: PromptLoader
    context_builder: ContextBuilder
    persistence: SessionPersistence
    session_manager: SessionManager
    artifact_manager: ArtifactManager
    workspace_manager: WorkspaceManager
    memory_service: MemoryService
    resource_manager: ResourceManager
    model_router: ModelRouter
    safety_policy: ToolSafetyPolicy
    approval_registry: ApprovalRegistry
    intent_analyzer: IntentAnalyzer
    task_planner: TaskPlanner
    execution_runner: ExecutionRunner
    response_synthesizer: ResponseSynthesizer

    def create_model_client(self, config):
        """Create a model client from config (delegates to app.models.factory)."""
        from app.models.factory import create_client

        return create_client(config)

    def get_provider_registry(self):
        """Get the provider registry (delegates to app.provider_registry)."""
        from app.provider_registry import get_provider_registry

        return get_provider_registry()

    def get_provider_spec(self, provider: str):
        """Get provider spec by key (delegates to app.provider_registry)."""
        return self.get_provider_registry().get_provider(provider)


_container_instance: ApplicationContainer | None = None


def bootstrap_system(
    data_dir: str = "data",
    prompts_dir: str = "prompts",
    db_url: str | None = None,
) -> ApplicationContainer:
    """Initialize and wire all system dependencies (Composition Root).

    Args:
        data_dir: Root directory for persistent data.
        prompts_dir: Directory containing Jinja2 markdown templates.
        db_url: Optional PostgreSQL connection URL. Falls back to
            ``JARVIS_DATABASE_URL`` env var.

    Returns:
        Configured ApplicationContainer singleton instance.
    """
    global _container_instance
    if _container_instance is not None:
        return _container_instance

    # Resolve database URL: explicit arg > env var > None
    resolved_db_url = db_url or os.environ.get("JARVIS_DATABASE_URL")

    # Select checkpointer: PostgresCheckpointer (prod) vs MemorySaverAdapter (dev)
    if resolved_db_url and resolved_db_url.startswith("postgresql"):
        try:
            get_postgres_checkpointer(resolved_db_url)
            logger.info("Using PostgresCheckpointer for session checkpointing")
        except Exception:  # noqa: BLE001 — graceful fallback
            MemorySaverAdapter()
            logger.warning(
                "Failed to create PostgresCheckpointer, falling back to MemorySaverAdapter"
            )
    else:
        MemorySaverAdapter()
        logger.info("Using MemorySaverAdapter for session checkpointing (dev mode)")

    logger.info("Initializing JARVIS Composition Root...")

    # 1. Event Bus & Telemetry
    bus = InMemoryAsyncBus()
    event_logger = EventLogger(bus=bus)
    tracer = Tracer(
        bus=bus,
        otel_enabled=os.environ.get("JARVIS_OTEL_ENABLED", "").lower() == "true",
        otel_endpoint=os.environ.get("JARVIS_OTEL_ENDPOINT"),
        otel_service_name=os.environ.get("JARVIS_OTEL_SERVICE_NAME"),
    )
    metrics = MetricsCollector()

    # 2. Prompts & Context
    prompt_loader = PromptLoader(prompts_dir=prompts_dir)
    context_builder = ContextBuilder(prompt_loader=prompt_loader)

    # 3. Session, Artifacts, Workspace Persistence
    persistence = SessionPersistence(data_dir=Path(data_dir) / "sessions", db_url=db_url)
    session_manager = SessionManager(persistence=persistence)
    artifact_manager = ArtifactManager(storage_dir=Path(data_dir) / "artifacts")
    workspace_manager = WorkspaceManager(workspace_root=".")

    # 4. Memory & Resources
    memory_service = MemoryService()
    resource_manager = ResourceManager()

    # 5. Model Router
    model_router = ModelRouter(resource_manager=resource_manager)

    # 6. Safety Policy & Guardrails
    safety_policy = ToolSafetyPolicy(auto_approve_sensitive=True)
    set_global_policy(safety_policy)
    # F5: persisted so a restart between a DESTRUCTIVE step pausing and a human
    # deciding cannot silently drop the pending approval and its paused plan.
    approval_registry = ApprovalRegistry(store_path=Path(data_dir) / "approvals.json")

    # 7. Cognitive Engine (Brain)
    intent_analyzer = IntentAnalyzer()
    task_planner = TaskPlanner()
    execution_runner = ExecutionRunner(event_bus=bus, safety_policy=safety_policy)
    # Composition-root wiring (ADR-011). ExecutionRunner dispatches tools by NAME, so the
    # registry must be populated here: unregistered names were silently marked COMPLETED
    # without executing anything (RISK-014).
    for _tool_name, _tool_fn in DEFAULT_TOOLSET.items():
        execution_runner.register_tool(_tool_name, _tool_fn)
    response_synthesizer = ResponseSynthesizer()

    _container_instance = ApplicationContainer(
        event_bus=bus,
        telemetry_logger=event_logger,
        tracer=tracer,
        metrics=metrics,
        prompt_loader=prompt_loader,
        context_builder=context_builder,
        persistence=persistence,
        session_manager=session_manager,
        artifact_manager=artifact_manager,
        workspace_manager=workspace_manager,
        memory_service=memory_service,
        resource_manager=resource_manager,
        model_router=model_router,
        safety_policy=safety_policy,
        approval_registry=approval_registry,
        intent_analyzer=intent_analyzer,
        task_planner=task_planner,
        execution_runner=execution_runner,
        response_synthesizer=response_synthesizer,
    )

    logger.info("JARVIS Composition Root bootstrapped successfully.")
    return _container_instance
