import httpx
import pytest

from fa_checker.adapters import ollama_client
from fa_checker.adapters.ollama_client import OllamaClientError, generate_ollama_response


def test_generate_ollama_response_returns_response_text(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(200, json={"response": " result "})

    monkeypatch.setattr(ollama_client.httpx, "post", fake_post)

    assert generate_ollama_response("prompt", model="test-model") == "result"


def test_generate_ollama_response_raises_for_non_2xx(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(500, json={"error": "bad"})

    monkeypatch.setattr(ollama_client.httpx, "post", fake_post)

    with pytest.raises(OllamaClientError, match="HTTP 500"):
        generate_ollama_response("prompt", model="test-model")


def test_generate_ollama_response_raises_for_network_error(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        raise httpx.ConnectError("connection failed")

    monkeypatch.setattr(ollama_client.httpx, "post", fake_post)

    with pytest.raises(OllamaClientError, match="Ollama request failed"):
        generate_ollama_response("prompt", model="test-model")


def test_generate_ollama_response_raises_for_missing_response_field(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(200, json={"not_response": "value"})

    monkeypatch.setattr(ollama_client.httpx, "post", fake_post)

    with pytest.raises(OllamaClientError, match="missing"):
        generate_ollama_response("prompt", model="test-model")


def test_generate_ollama_response_raises_for_empty_response(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(200, json={"response": "   "})

    monkeypatch.setattr(ollama_client.httpx, "post", fake_post)

    with pytest.raises(OllamaClientError, match="empty"):
        generate_ollama_response("prompt", model="test-model")


def test_generate_ollama_response_can_request_json_format(monkeypatch) -> None:
    captured_payload = {}

    def fake_post(url, json, timeout):
        captured_payload.update(json)
        return httpx.Response(200, json={"response": "{}"})

    monkeypatch.setattr(ollama_client.httpx, "post", fake_post)

    generate_ollama_response("prompt", model="test-model", format_json=True)

    assert captured_payload["format"] == "json"


def test_generate_ollama_response_can_set_temperature(monkeypatch) -> None:
    captured_payload = {}

    def fake_post(url, json, timeout):
        captured_payload.update(json)
        return httpx.Response(200, json={"response": "{}"})

    monkeypatch.setattr(ollama_client.httpx, "post", fake_post)

    generate_ollama_response("prompt", model="test-model", temperature=0.0)

    assert captured_payload["options"] == {"temperature": 0.0}
