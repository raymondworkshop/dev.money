"""Swappable LLM provider adapter for wiki compile proposals."""

from __future__ import annotations

import json
import os
import re
import sys
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
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 4096
DEFAULT_JSON_RETRY_ATTEMPTS = 2
JSON_RETRY_PROMPT = (
    "Your previous response was invalid or incomplete JSON. "
    "Return ONLY one valid JSON object matching the requested contract. "
    "No markdown fences, no commentary."
)
PLACEHOLDER_MODELS = {"", "mlx-model", "local-model"}
VALID_PROVIDERS = frozenset({"mlx", "gemini", "openai", "fixture"})


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


def normalize_provider(name: str) -> str:
    value = name.strip().lower()
    return value if value in VALID_PROVIDERS - {"fixture"} else "mlx"


def default_provider() -> str:
    load_env()
    return normalize_provider(os.environ.get("LLM_PROVIDER", "mlx"))


def is_provider_configured(provider: str) -> bool:
    load_env()
    name = normalize_provider(provider)
    if name == "mlx":
        return True
    if name == "gemini":
        return bool(os.environ.get("GEMINI_API_KEY", "").strip())
    if name == "openai":
        return bool(os.environ.get("OPENAI_API_KEY", "").strip())
    return False


def fallback_enabled() -> bool:
    load_env()
    return os.environ.get("LLM_FALLBACK_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def fallback_provider_chain(primary: str | None = None) -> list[str]:
    """Primary provider first, then configured fallbacks (deduped)."""

    load_env()
    primary_name = normalize_provider(primary or default_provider())
    if not fallback_enabled():
        return [primary_name]

    explicit = os.environ.get("LLM_FALLBACK_PROVIDERS", "").strip()
    if explicit:
        candidates = [
            normalize_provider(part)
            for part in explicit.split(",")
            if part.strip()
        ]
    elif primary_name == "gemini":
        candidates = ["mlx"]
    else:
        candidates = []

    chain = [primary_name]
    for candidate in candidates:
        if candidate in chain:
            continue
        if candidate == "mlx" or is_provider_configured(candidate):
            chain.append(candidate)
    return chain


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
    if provider == "gemini":
        return os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
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


def resolve_temperature() -> float:
    load_env()
    return float(os.environ.get("LLM_TEMPERATURE", str(DEFAULT_TEMPERATURE)))


def resolve_max_tokens() -> int:
    load_env()
    return int(os.environ.get("LLM_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))


def resolve_json_retry_attempts() -> int:
    load_env()
    return max(
        1,
        int(
            os.environ.get(
                "LLM_JSON_RETRY_ATTEMPTS",
                str(DEFAULT_JSON_RETRY_ATTEMPTS),
            )
        ),
    )


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
    temperature: float = DEFAULT_TEMPERATURE


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
        self.temperature = resolve_temperature()
        self.max_tokens = resolve_max_tokens()

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
            "max_tokens": self.max_tokens,
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


class GeminiProvider:
    """Live provider for Google Gemini generateContent API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        load_env()
        self.provider = "gemini"
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.model = model or resolve_model("gemini")
        self.timeout = timeout or int(os.environ.get("LLM_TIMEOUT_SECONDS", "360"))
        self.retry_attempts = max(1, int(os.environ.get("LLM_RETRY_ATTEMPTS", "2")))
        self.retry_backoff = max(1, int(os.environ.get("LLM_RETRY_BACKOFF_SECONDS", "5")))
        self.max_tokens = resolve_max_tokens()

    def complete(self, request: LLMRequest) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini calls.")

        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": self.max_tokens,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        }
        if request.system:
            payload["system_instruction"] = {"parts": [{"text": request.system}]}

        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        last_error: Exception | None = None
        for attempt in range(1, self.retry_attempts + 1):
            http_request = urllib.request.Request(
                endpoint,
                data=body,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                candidates = data.get("candidates") or []
                if not candidates:
                    raise RuntimeError("Gemini API returned no candidates.")
                candidate = candidates[0]
                if candidate.get("finishReason") == "SAFETY":
                    raise RuntimeError("Gemini response blocked by safety filters.")
                return str(candidate["content"]["parts"][0]["text"])
            except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
                last_error = exc
                if attempt >= self.retry_attempts:
                    break
                time.sleep(self.retry_backoff)

        raise RuntimeError(f"gemini model {self.model}: {last_error}") from last_error


class FallbackProvider:
    """Try providers in order until one succeeds."""

    def __init__(self, providers: list[LLMProvider], names: list[str]) -> None:
        if len(providers) != len(names):
            raise ValueError("providers and names must have the same length.")
        self.providers = providers
        self.names = names
        self.provider = names[0]

    def complete(self, request: LLMRequest) -> str:
        last_error: Exception | None = None
        for index, (name, provider) in enumerate(zip(self.names, self.providers)):
            try:
                return provider.complete(request)
            except Exception as exc:
                last_error = exc
                if index < len(self.providers) - 1:
                    print(
                        f"[llm_provider] {name} failed: {exc}; falling back to {self.names[index + 1]}",
                        file=sys.stderr,
                    )
        raise RuntimeError(
            f"All LLM providers failed ({', '.join(self.names)}): {last_error}"
        ) from last_error


def _single_provider(name: str) -> LLMProvider:
    if name == "gemini":
        return GeminiProvider()
    if name in {"mlx", "openai"}:
        return OpenAICompatibleProvider(provider=name)
    raise ValueError(f"Unknown LLM provider: {name}")


def proposal_from_provider(provider: LLMProvider, request: LLMRequest) -> dict[str, Any]:
    """Ask a provider for a compile proposal and parse the strict JSON response."""

    attempts = resolve_json_retry_attempts()
    current_request = request
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            text = provider.complete(current_request).strip()
            return extract_json_object(text)
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= attempts:
                break
            current_request = LLMRequest(
                system=current_request.system,
                prompt=f"{current_request.prompt}\n\n{JSON_RETRY_PROMPT}",
                temperature=current_request.temperature,
            )

    raise ValueError(
        f"LLM provider returned invalid JSON after {attempts} attempt(s)."
    ) from last_error


def build_provider(name: str | None = None, *, fixture: str | dict[str, Any] | None = None) -> LLMProvider:
    """Factory used by CLI code; tests should pass FixtureProvider directly when possible."""

    raw_name = (name or default_provider()).strip().lower()
    if raw_name == "fixture":
        if fixture is None:
            raise ValueError("fixture provider requires fixture content.")
        return FixtureProvider(fixture)

    provider_name = normalize_provider(raw_name)
    chain = fallback_provider_chain(provider_name)
    providers = [_single_provider(item) for item in chain]
    if len(providers) == 1:
        return providers[0]
    return FallbackProvider(providers, chain)
