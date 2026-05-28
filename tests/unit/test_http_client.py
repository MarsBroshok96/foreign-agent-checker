import httpx
import pytest

from fa_checker.adapters import http_client
from fa_checker.adapters.http_client import HttpFetchError, fetch_bytes, fetch_text


def test_fetch_text_returns_successful_response_body(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        return httpx.Response(200, text="<html>ok</html>")

    monkeypatch.setattr(http_client.httpx, "get", fake_get)

    assert fetch_text("https://www.rambler.ru/example") == "<html>ok</html>"


def test_fetch_text_raises_for_non_2xx_response(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        return httpx.Response(404, text="not found")

    monkeypatch.setattr(http_client.httpx, "get", fake_get)

    with pytest.raises(HttpFetchError, match="HTTP 404"):
        fetch_text("https://www.rambler.ru/example")


def test_fetch_text_raises_for_network_error(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("connection failed")

    monkeypatch.setattr(http_client.httpx, "get", fake_get)

    with pytest.raises(HttpFetchError, match="Failed to fetch URL"):
        fetch_text("https://www.rambler.ru/example")


def test_fetch_text_raises_for_empty_body(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        return httpx.Response(200, text="   ")

    monkeypatch.setattr(http_client.httpx, "get", fake_get)

    with pytest.raises(HttpFetchError, match="empty response body"):
        fetch_text("https://www.rambler.ru/example")


def test_fetch_bytes_returns_successful_response_content(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        return httpx.Response(200, content=b"xlsx-bytes")

    monkeypatch.setattr(http_client.httpx, "get", fake_get)

    assert fetch_bytes("https://minjust.gov.ru/export.xlsx") == b"xlsx-bytes"


def test_fetch_bytes_raises_for_non_2xx_response(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        return httpx.Response(500, content=b"error")

    monkeypatch.setattr(http_client.httpx, "get", fake_get)

    with pytest.raises(HttpFetchError, match="HTTP 500"):
        fetch_bytes("https://minjust.gov.ru/export.xlsx")


def test_fetch_bytes_raises_for_empty_content(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        return httpx.Response(200, content=b"")

    monkeypatch.setattr(http_client.httpx, "get", fake_get)

    with pytest.raises(HttpFetchError, match="empty response content"):
        fetch_bytes("https://minjust.gov.ru/export.xlsx")
