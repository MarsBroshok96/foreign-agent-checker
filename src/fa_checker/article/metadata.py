"""Small deterministic URL helpers for article metadata."""

from urllib.parse import urlparse


def extract_source_domain(url: str) -> str:
    """Return the normalized hostname for a valid HTTP(S) URL."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        msg = "URL must be an absolute http or https URL with a hostname."
        raise ValueError(msg)
    return parsed.hostname.rstrip(".").lower()


def is_rambler_url(url: str) -> bool:
    """Return whether the URL belongs to rambler.ru or one of its subdomains."""
    try:
        hostname = extract_source_domain(url)
    except ValueError:
        return False
    return hostname == "rambler.ru" or hostname.endswith(".rambler.ru")

