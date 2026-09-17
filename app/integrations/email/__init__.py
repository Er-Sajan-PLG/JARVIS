"""Email integration package."""
from app.integrations.email.client import EmailClient, EmailConfig
from app.integrations.email.reader import EmailReader
from app.integrations.email.sender import EmailSender

__all__ = ["EmailClient", "EmailConfig", "EmailReader", "EmailSender"]
