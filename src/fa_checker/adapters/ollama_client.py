"""Small synchronous Ollama client helpers."""

from typing import Any

import httpx


class OllamaClientError(RuntimeError):
    """Raised when a local Ollama generation request fails."""


def generate_ollama_response(
    prompt: str,
    model: str,
    base_url: str = "http://localhost:11434",
    timeout_seconds: float = 60.0,
    format_json: bool = False,
    temperature: float | None = None,
) -> str:
    """Generate a non-streaming response from a local Ollama model."""
    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if format_json:
        payload["format"] = "json"
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    try:
        response = httpx.post(url, json=payload, timeout=timeout_seconds)
    except httpx.HTTPError as exc:
        msg = f"Ollama request failed: {exc}"
        raise OllamaClientError(msg) from exc

    if not 200 <= response.status_code < 300:
        msg = f"Ollama request failed with HTTP {response.status_code}."
        raise OllamaClientError(msg)

    try:
        data: dict[str, Any] = response.json()
    except ValueError as exc:
        msg = "Ollama response was not valid JSON."
        raise OllamaClientError(msg) from exc

    raw_text = data.get("response")
    if not isinstance(raw_text, str):
        msg = "Ollama response JSON is missing a string 'response' field."
        raise OllamaClientError(msg)
    text = raw_text.strip()
    if not text:
        msg = "Ollama response was empty."
        raise OllamaClientError(msg)
    return text


class OllamaClient:
    """Compatibility wrapper around generate_ollama_response."""

    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        self.model = model
        self.base_url = base_url

    def generate(self, prompt: str) -> str:
        return generate_ollama_response(
            prompt=prompt,
            model=self.model,
            base_url=self.base_url,
        )
