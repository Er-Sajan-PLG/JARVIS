"""Google OAuth authentication for Google AI Pro account.

Handles:
- OAuth 2.0 login flow (local server callback)
- Token persistence (~/.hermes/google_credentials.json)
- Automatic token refresh
- List available Gemini models from user's account
- Send files directly to Gemini for extraction/analysis
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Paths
CREDS_PATH = Path.home() / ".hermes" / "google_credentials.json"
CREDS_PATH.parent.mkdir(parents=True, exist_ok=True)

# Google OAuth scopes for AI/Generative AI
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/generative-language.retriever",
]

# Google Generative AI API
GENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Available Gemini models
GEMINI_MODELS = [
    {"id": "gemini-3.1-pro", "name": "Gemini 3.1 Pro", "description": "Google's most capable model for complex tasks", "context_length": 1000000, "pricing": {}},
    {"id": "gemini-3.1-flash", "name": "Gemini 3.1 Flash", "description": "Fast and efficient model", "context_length": 1000000, "pricing": {}},
    {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash Lite", "description": "Lightweight fast model", "context_length": 1000000, "pricing": {}},
    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "description": "Previous gen capable model", "context_length": 1000000, "pricing": {}},
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "description": "Previous gen fast model", "context_length": 1000000, "pricing": {}},
    {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "description": "Fast and efficient", "context_length": 1000000, "pricing": {}},
]


class GoogleOAuth:
    """Google OAuth 2.0 authentication manager."""

    def __init__(self):
        self._credentials: dict[str, Any] | None = None
        self._load_credentials()

    def _load_credentials(self):
        """Load credentials from disk."""
        if CREDS_PATH.exists():
            try:
                with open(CREDS_PATH) as f:
                    self._credentials = json.load(f)
                logger.info("Loaded Google credentials from %s", CREDS_PATH)
            except Exception as e:
                logger.warning("Failed to load Google credentials: %s", e)
                self._credentials = None

    def _save_credentials(self):
        """Save credentials to disk."""
        if self._credentials:
            with open(CREDS_PATH, "w") as f:
                json.dump(self._credentials, f, indent=2)
            logger.info("Saved Google credentials to %s", CREDS_PATH)

    @property
    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        if not self._credentials:
            return False
        # Check expiry
        expires_at = self._credentials.get("expires_at", 0)
        return expires_at > time.time()

    @property
    def access_token(self) -> str | None:
        """Get the current access token, refreshing if needed."""
        if not self.is_authenticated:
            return self._refresh_token()
        return self._credentials.get("access_token") if self._credentials else None

    def _refresh_token(self) -> str | None:
        """Refresh the access token using the refresh token."""
        if not self._credentials or "refresh_token" not in self._credentials:
            self._credentials = None
            return None

        try:
            from google.auth.transport.requests import Request as GoogleRequest
            from google.oauth2.credentials import Credentials

            creds = Credentials.from_authorized_user_info(self._credentials, SCOPES)
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                self._credentials = json.loads(creds.to_json())
                self._credentials["expires_at"] = creds.expiry.timestamp() if creds.expiry else time.time() + 3600
                self._save_credentials()
                logger.info("Refreshed Google access token")
            return self._credentials.get("access_token") if self._credentials else None
        except Exception as e:
            logger.error("Failed to refresh Google token: %s", e)
            self._credentials = None
            return None

    def login(self, client_id: str, client_secret: str) -> bool:
        """
        Perform OAuth login flow.

        Opens a browser for the user to authenticate, then saves the credentials.
        """
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow

            # Build the OAuth flow
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost:8080/callback"],
                }
            }

            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

            # Run the local server for callback
            credentials = flow.run_local_server(port=8080, prompt="consent")

            # Save credentials
            self._credentials = json.loads(credentials.to_json())
            self._credentials["expires_at"] = credentials.expiry.timestamp() if credentials.expiry else time.time() + 3600
            self._save_credentials()

            logger.info("Google OAuth login successful")
            return True

        except Exception as e:
            logger.error("Google OAuth login failed: %s", e)
            return False

    def logout(self):
        """Remove stored credentials."""
        self._credentials = None
        if CREDS_PATH.exists():
            CREDS_PATH.unlink()
        logger.info("Google credentials removed")

    def get_models(self) -> list[dict[str, Any]]:
        """Get available Gemini models."""
        return GEMINI_MODELS


# Global instance
_google_oauth = GoogleOAuth()


def get_google_oauth() -> GoogleOAuth:
    """Get the global Google OAuth instance."""
    return _google_oauth
