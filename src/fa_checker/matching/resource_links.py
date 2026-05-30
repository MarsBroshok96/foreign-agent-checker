"""Deterministic full-URL checks for registry resource links."""

import re
from urllib.parse import urlsplit, urlunsplit

from fa_checker.domain.models import Article, RegistryEntry, ResourceLinkMatch


def normalize_resource_url(url: str) -> str:
    """Normalize a resource URL for deterministic full-link comparison."""
    value = url.strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""

    path = parsed.path.rstrip("/") if parsed.path != "/" else ""

    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.query,
            "",
        )
    )


def find_resource_link_matches(
    article: Article,
    registry_entries: list[RegistryEntry],
) -> list[ResourceLinkMatch]:
    """Find exact full-URL matches between article body links and registry resources."""
    normalized_article_links = [
        (link, normalized)
        for link in article.links
        if (normalized := normalize_resource_url(link))
    ]
    matches: list[ResourceLinkMatch] = []
    seen: set[tuple[str | None, str, str, str]] = set()

    for article_link, normalized_article_url in normalized_article_links:
        for entry in registry_entries:
            for registry_url in _resource_urls(entry):
                normalized_registry_url = normalize_resource_url(registry_url)
                if (
                    not normalized_registry_url
                    or normalized_article_url != normalized_registry_url
                ):
                    continue
                key = (
                    entry.registry_id,
                    entry.full_name,
                    normalized_article_url,
                    normalized_registry_url,
                )
                if key in seen:
                    continue
                seen.add(key)
                matches.append(
                    ResourceLinkMatch(
                        registry_id=entry.registry_id,
                        entity_name=entry.full_name,
                        entity_type=entry.entity_type.value,
                        article_url=article_link,
                        registry_url=registry_url,
                        normalized_article_url=normalized_article_url,
                        normalized_registry_url=normalized_registry_url,
                    )
                )

    return matches


def _resource_urls(entry: RegistryEntry) -> list[str]:
    raw_urls = entry.raw_fields.get("resource_urls")
    if isinstance(raw_urls, list):
        return [str(url).strip() for url in raw_urls if str(url).strip()]
    if isinstance(raw_urls, str):
        return [
            part.strip()
            for part in re.split(r"[\s;,]+", raw_urls)
            if part.strip()
        ]
    return []
