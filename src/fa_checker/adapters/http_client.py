"""Small synchronous HTTP helper for article loading."""

import httpx

USER_AGENT = (
    "foreign-agent-checker/0.1 "
    "(compliance-assistance tool; contact: local-development)"
)


class HttpFetchError(RuntimeError):
    """Raised when HTTP text fetching fails."""


def fetch_text(url: str, timeout_seconds: float = 10.0) -> str:
    """Fetch text content from a URL using a plain synchronous HTTP request."""
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=timeout_seconds,
        )
    except httpx.HTTPError as exc:
        msg = f"Failed to fetch URL {url!r}: {exc}"
        raise HttpFetchError(msg) from exc

    if not 200 <= response.status_code < 300:
        msg = f"Failed to fetch URL {url!r}: HTTP {response.status_code}"
        raise HttpFetchError(msg)

    if not response.text.strip():
        msg = f"Failed to fetch URL {url!r}: empty response body"
        raise HttpFetchError(msg)

    return response.text


class HttpClient:
    """Compatibility wrapper around fetch_text."""

    def get_text(self, url: str) -> str:
        return fetch_text(url)
