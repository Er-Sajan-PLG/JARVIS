"""Brief service for generating morning summaries."""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BriefConfig:
    """Morning brief configuration."""
    enabled: bool = False
    time: str = "08:00"
    delivery_channels: list[str] = field(default_factory=lambda: ["slack"])
    slack_webhook: str = ""
    email_recipient: str = ""

    @classmethod
    def from_env(cls) -> "BriefConfig":
        import os
        channels = os.getenv("JARVIS_BRIEF_DELIVERY", "slack").split(",")
        return cls(
            enabled=os.getenv("JARVIS_BRIEF_ENABLED", "false").lower() == "true",
            time=os.getenv("JARVIS_BRIEF_TIME", "08:00"),
            delivery_channels=[c.strip() for c in channels],
            slack_webhook=os.getenv("JARVIS_BRIEF_SLACK_WEBHOOK", ""),
            email_recipient=os.getenv("JARVIS_BRIEF_EMAIL", ""),
        )


class BriefService:
    """Service for generating and delivering morning briefs."""
    
    def __init__(self, config: BriefConfig | None = None):
        self.config = config or BriefConfig.from_env()
    
    async def generate_brief(self) -> dict[str, Any]:
        """Generate the morning brief content."""
        brief = {
            "timestamp": datetime.now().isoformat(),
            "greeting": self._get_greeting(),
            "sections": [],
        }
        
        # Memory summary
        brief["sections"].append({
            "title": "Memory",
            "content": await self._get_memory_summary(),
        })
        
        # Pending approvals
        brief["sections"].append({
            "title": "Pending Approvals",
            "content": await self._get_pending_approvals(),
        })
        
        # Task summary
        brief["sections"].append({
            "title": "Recent Activity",
            "content": await self._get_recent_activity(),
        })
        
        return brief
    
    def _get_greeting(self) -> str:
        """Get time-appropriate greeting."""
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning."
        elif hour < 18:
            return "Good afternoon."
        return "Good evening."
    
    async def _get_memory_summary(self) -> str:
        """Get summary of new memories."""
        try:
            from app.bootstrap import bootstrap_system
            container = bootstrap_system()
            count = container.memory_service._manager.count()
            return f"{count} memories stored."
        except Exception:
            return "Memory data unavailable."
    
    async def _get_pending_approvals(self) -> str:
        """Get pending HITL approvals."""
        return "No pending approvals (HITL not active)."
    
    async def _get_recent_activity(self) -> str:
        """Get recent task activity."""
        return "No recent activity."
    
    async def deliver(self, brief: dict[str, Any]) -> dict[str, Any]:
        """Deliver brief via configured channels."""
        results = {}
        
        for channel in self.config.delivery_channels:
            if channel == "slack":
                results["slack"] = await self._deliver_slack(brief)
            elif channel == "email":
                results["email"] = await self._deliver_email(brief)
        
        return results
    
    async def _deliver_slack(self, brief: dict[str, Any]) -> bool:
        """Deliver brief to Slack webhook."""
        if not self.config.slack_webhook:
            return False
        
        try:
            import requests
            
            text = self._format_brief_text(brief)
            response = requests.post(
                self.config.slack_webhook,
                json={"text": text},
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            logger.error("Slack delivery error: %s", e)
            return False
    
    async def _deliver_email(self, brief: dict[str, Any]) -> bool:
        """Deliver brief via email."""
        if not self.config.email_recipient:
            return False
        
        try:
            from app.integrations.email.tools import send_email
            text = self._format_brief_text(brief)
            result = await send_email(
                to=self.config.email_recipient,
                subject=f"Morning Brief - {datetime.now().strftime('%Y-%m-%d')}",
                body=text,
            )
            return result["success"]
        except Exception as e:
            logger.error("Email delivery error: %s", e)
            return False
    
    def _format_brief_text(self, brief: dict[str, Any]) -> str:
        """Format brief as plain text."""
        lines = [brief["greeting"], ""]
        
        for section in brief["sections"]:
            lines.append(f"**{section['title']}**")
            lines.append(section["content"])
            lines.append("")
        
        return "\n".join(lines)
