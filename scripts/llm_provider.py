"""Swappable LLM provider adapter for wiki compile proposals."""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMRequest:
    """Prompt payload passed from deterministic harness code to an LLM provider."""

    system: str
    prompt: str
    temperature: float = 0.1


class LLMProvider(Protocol):
    """Small boundary that live providers and test fixtures both implement."""

    def complete(self, request: LLMRequest) -> str:
        """Return the raw model text for a request."""


class FixtureProvider:
    """Deterministic provider for tests and dry-run fixtures."""

    def __init__(self, response: str | dict[str, Any]) -> None:
        self.response = response
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> str:
        self.requests.append(request)
        if isinstance(self.response, str):
            return self.response
        return json.dumps(self.response, ensure_ascii=False)


class OpenAICompatibleProvider:
    """Live provider for OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = 120,
    ) -> None:
        self.base_url = (base_url or os.environ.get("DEV_MONEY_LLM_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("DEV_MONEY_LLM_MODEL", "gpt-4o-mini")
        self.timeout = timeout

    def complete(self, request: LLMRequest) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for live LLM calls.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": request.temperature,
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return str(data["choices"][0]["message"]["content"])


def proposal_from_provider(provider: LLMProvider, request: LLMRequest) -> dict[str, Any]:
    """Ask a provider for a compile proposal and parse the strict JSON response."""

    text = provider.complete(request).strip()
    try:
        proposal = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM provider returned invalid JSON.") from exc
    if not isinstance(proposal, dict):
        raise ValueError("LLM provider must return a JSON object.")
    return proposal


def build_provider(name: str = "openai", *, fixture: str | dict[str, Any] | None = None) -> LLMProvider:
    """Factory used by CLI code; tests should pass FixtureProvider directly when possible."""

    if name == "fixture":
        if fixture is None:
            raise ValueError("fixture provider requires fixture content.")
        return FixtureProvider(fixture)
    if name == "openai":
        return OpenAICompatibleProvider()
    raise ValueError(f"Unknown LLM provider: {name}")
