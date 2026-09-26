"""Web-search runner tool (Migration Plan Step 2).

Exa-backed ``web_search`` for the ExecutionRunner. Registered in
``DEFAULT_TOOLSET`` only when ``JARVIS_WEB_SEARCH=1`` (default OFF); see
``app/tools/__init__.py``. Read-only network egress, hence ``SAFE`` tier.

RULES FOR THIS MODULE: new code only. No request-path, prompt, config, or
contract changes.
"""

from __future__ import annotations

import os
from typing import Any

import aiohttp

from app.domain import SafetyTier
from app.guardrails import safety_gate

EXA_SEARCH_ENDPOINT = "https://api.exa.ai/search"
RESULT_TRUNCATE_AT = 500


def _excerpt(result: dict[str, Any]) -> str:
    """Best-effort text extraction across Exa response shapes."""
    text = result.get("text") or result.get("snippet") or ""
    highlights = result.get("highlights")
    if not text and isinstance(highlights, list):
        text = " ".join(str(h) for h in highlights)
    text = str(text)
    if len(text) > RESULT_TRUNCATE_AT:
        text = text[:RESULT_TRUNCATE_AT] + "...[truncated]"
    return text


def _format_results(results: list[Any], max_results: int) -> str:
    lines: list[str] = []
    for index, item in enumerate(results[:max_results], start=1):
        result = item if isinstance(item, dict) else {"text": str(item)}
        title = str(result.get("title") or "(untitled)")
        url = str(result.get("url") or "(no url)")
        lines.append(f"{index}. {title}\n{url}\n{_excerpt(result)}")
    return "\n\n".join(lines)


@safety_gate(tier=SafetyTier.SAFE, description="Web search via Exa")
async def web_search(query: str, max_results: int = 5, timeout_sec: float = 5) -> str:
    """Search the web and return newline-separated results (never raises)."""
    api_key = os.getenv("EXA_API_KEY", "").strip()
    if not api_key:
        return "Search failed: missing EXA_API_KEY"
    try:
        timeout = aiohttp.ClientTimeout(total=timeout_sec)
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.post(
                EXA_SEARCH_ENDPOINT,
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={"query": query, "numResults": max_results},
            ) as response,
        ):
            response.raise_for_status()
            payload: Any = await response.json()
        results = payload.get("results", []) if isinstance(payload, dict) else []
        if not results:
            return "Search failed: no results"
        output = _format_results(results, max_results)
        # Redact the key in case a result echoes request metadata.
        return output.replace(api_key, "[REDACTED]")
    except Exception as err:  # noqa: BLE001 - tool contract: return errors as text
        return f"Search failed: {err}".replace(api_key, "[REDACTED]")
