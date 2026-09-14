"""Google GenAI integration using OAuth credentials.

Provides access to Gemini models through the user's Google AI Pro account.
Supports native file uploads (PDFs, images, etc.) for extraction.
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.google_oauth import get_google_oauth

logger = logging.getLogger(__name__)


class GoogleGenAIClient:
    """Client for Google Gemini models using OAuth authentication."""

    def __init__(self, model: str = "gemini-3.1-pro"):
        self._model = model
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize the GenAI client with OAuth credentials."""
        try:
            from google import genai

            oauth = get_google_oauth()
            if not oauth.is_authenticated:
                logger.warning("Google OAuth not authenticated")
                return

            # Create GenAI client - OAuth is handled via Application Default Credentials
            # or we can pass the token directly
            token = oauth.access_token
            if token:
                self._client = genai.Client(api_key=token)
                logger.info("Google GenAI client initialized for model: %s", self._model)
            else:
                logger.warning("No access token available")

        except Exception as e:
            logger.error("Failed to initialize Google GenAI client: %s", e)
            self._client = None

    @property
    def is_available(self) -> bool:
        """Check if the client is available."""
        return self._client is not None

    def generate(self, messages: list[dict[str, Any]], **kwargs) -> dict[str, Any]:
        """Generate a response using Gemini."""
        if not self._client:
            raise RuntimeError("Google GenAI client not initialized")

        # Convert messages to Gemini format
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "assistant":
                role = "model"
            contents.append({"role": role, "parts": [{"text": content}]})

        # Generate
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
        )

        return {
            "content": response.text or "",
            "model": self._model,
            "tokens_used": None,
            "finish_reason": "stop",
        }

    def upload_file(self, file_path: str, mime_type: str | None = None) -> Any:
        """Upload a file to Gemini for analysis."""
        if not self._client:
            raise RuntimeError("Google GenAI client not initialized")

        # Upload file
        file = self._client.files.upload(
            file=file_path,
            config={"mime_type": mime_type} if mime_type else None,
        )
        return file

    def analyze_file(self, file_path: str, query: str, mime_type: str | None = None) -> str:
        """Upload a file and ask Gemini to analyze it."""
        if not self._client:
            raise RuntimeError("Google GenAI client not initialized")

        # Upload file
        file = self._client.files.upload(
            file=file_path,
            config={"mime_type": mime_type} if mime_type else None,
        )

        # Generate with file
        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                {"role": "user", "parts": [
                    {"file_data": {"file_uri": file.uri or "", "mime_type": file.mime_type or ""}},
                    {"text": query},
                ]},
            ],
        )

        return response.text or ""


def get_gemini_client(model: str = "gemini-3.1-pro") -> GoogleGenAIClient | None:
    """Get a Gemini client if OAuth is authenticated."""
    client = GoogleGenAIClient(model)
    if client.is_available:
        return client
    return None
