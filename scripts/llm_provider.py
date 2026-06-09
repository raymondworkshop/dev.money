"""Swappable LLM provider adapter for wiki compile proposals."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

DEFAULT_MLX_URL = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_MLX_MODEL = "mlx-community/gemma-4-e4b-it-4bit"
DEFAULT_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
PLACEHOLDER_MODELS = {"", "mlx-model", "local-model"}
VALID_PROVIDERS = frozenset({"mlx", "openai", "fixture"})


def load_env(env_path: Path | None = None) -> None:
    """Load key=value pairs from .env into os.environ."""

    path = env_path or Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def default_provider() -> str:
    load_env()
    name = os.environ.get("LLM_PROVIDER", "mlx").strip().lower()
    return name if name in VALID_PROVIDERS else "mlx"


def chat_completions_url(provider: str) -> str:
    load_env()
    explicit = os.environ.get("LLM_URL", "").strip()
    if provider == "openai":
        return explicit or os.environ.get("DEV_MONEY_LLM_URL", DEFAULT_OPENAI_URL).rstrip("/")
    if explicit:
        return explicit.rstrip("/")
    return DEFAULT_MLX_URL


def openai_compatible_api_base(provider: str) -> str:
    url = chat_completions_url(provider).rstrip("/")
    suffix = "/chat/completions"
    if url.endswith(suffix):
        return url[: -len(suffix)]
    return url


def resolve_model(provider: str) -> str:
    load_env()
    configured = os.environ.get("LLM_MODEL", "").strip()
    if provider == "openai":
        if configured and configured not in PLACEHOLDER_MODELS:
            return configured
        return os.environ.get("DEV_MONEY_LLM_MODEL", DEFAULT_OPENAI_MODEL)

    if configured and configured not in PLACEHOLDER_MODELS:
        return configured

    models_url = f"{openai_compatible_api_base(provider)}/models"
    try:
        request = urllib.request.Request(models_url, method="GET")
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        models = data.get("data", [])
        if models:
            model_id = str(models[0].get("id", "")).strip()
            if model_id:
                return model_id
    except Exception:
        pass
    return DEFAULT_MLX_MODEL


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from raw model text, including fenced blocks."""

    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            raise ValueError("LLM provider returned invalid JSON.") from None
        payload = json.loads(match.group(0))

    if not isinstance(payload, dict):
        raise ValueError("LLM provider must return a JSON object.")
    return payload


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
    """Live provider for MLX and other OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        *,
        provider: str = "mlx",
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        load_env()
        self.provider = provider
        self.base_url = (base_url or chat_completions_url(provider)).rstrip("/")
        if self.base_url.endswith("/chat/completions"):
            self.endpoint = self.base_url
        else:
            self.endpoint = f"{self.base_url}/chat/completions"
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or resolve_model(provider)
        self.timeout = timeout or int(os.environ.get("LLM_TIMEOUT_SECONDS", "360"))
        self.retry_attempts = max(1, int(os.environ.get("LLM_RETRY_ATTEMPTS", "2")))
        self.retry_backoff = max(1, int(os.environ.get("LLM_RETRY_BACKOFF_SECONDS", "5")))

    def complete(self, request: LLMRequest) -> str:
        if self.provider == "openai" and not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for live OpenAI calls.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": request.temperature,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key or 'no-key'}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(1, self.retry_attempts + 1):
            http_request = urllib.request.Request(
                self.endpoint,
                data=body,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return str(data["choices"][0]["message"]["content"])
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt >= self.retry_attempts:
                    break
                time.sleep(self.retry_backoff)

        raise RuntimeError(
            f"{self.provider} at {self.endpoint}: {last_error}"
        ) from last_error


def proposal_from_provider(provider: LLMProvider, request: LLMRequest) -> dict[str, Any]:
    """Ask a provider for a compile proposal and parse the strict JSON response."""

    text = provider.complete(request).strip()
    return extract_json_object(text)


def build_provider(name: str | None = None, *, fixture: str | dict[str, Any] | None = None) -> LLMProvider:
    """Factory used by CLI code; tests should pass FixtureProvider directly when possible."""

    provider_name = (name or default_provider()).lower()
    if provider_name == "fixture":
        if fixture is None:
            raise ValueError("fixture provider requires fixture content.")
        return FixtureProvider(fixture)
    if provider_name in {"mlx", "openai"}:
        return OpenAICompatibleProvider(provider=provider_name)
    raise ValueError(f"Unknown LLM provider: {provider_name}")
