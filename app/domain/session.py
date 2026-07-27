"""Pure Domain Entities: Session State & User Preferences.

Zero infrastructure or framework dependencies. Modern Python 3.11+ syntax.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class UserPreferences:
    """Configurable user preferences for session execution."""
    active_model_id: str = "omni"
    use_developer_keys: bool = False
    hitl_auto_approve_sensitive: bool = True
    theme: str = "dark"
    custom_instructions: str = ""


@dataclass
class SessionState:
    """Live session state entity."""
    session_id: str
    user_id: str = "default_user"
    active_conversation_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    preferences: UserPreferences = field(default_factory=UserPreferences)
    metadata: dict[str, Any] = field(default_factory=dict)
