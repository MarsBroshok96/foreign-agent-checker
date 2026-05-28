"""HTML-to-Article extraction helpers."""

import json
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import trafilatura
from bs4 import BeautifulSoup

from fa_checker.article.metadata import extract_source_domain
from fa_checker.article.normalizer import normalize_for_display
from fa_checker.domain.models import Article


class ArticleExtractionError(RuntimeError):
    """Raised when article text cannot be extracted from HTML."""


def extract_article_from_html(url: str, html: str) -> Article:
    """Extract an Article domain object from an already fetched HTML document."""
    soup = BeautifulSoup(html, "html.parser")
    text = normalize_for_display(_extract_text(html, soup))
    if not text:
        msg = f"Could not extract article text from {url!r}."
        raise ArticleExtractionError(msg)

    return Article(
        url=url,
        source_domain=extract_source_domain(url),
        title=_extract_title(soup),
        author=_extract_author(soup),
        published_at=_extract_published_at(soup),
        text=text,
        links=_extract_links(url, soup),
    )


def _extract_title(soup: BeautifulSoup) -> str | None:
    og_title = _meta_content(soup, property_name="og:title")
    if og_title:
        return og_title
    title = soup.find("title")
    if title and title.get_text(strip=True):
        return title.get_text(strip=True)
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    return None


def _extract_author(soup: BeautifulSoup) -> str | None:
    for value in (
        _meta_content(soup, name="author"),
        _meta_content(soup, property_name="article:author"),
        _json_ld_author(soup),
    ):
        if value:
            return value
    return None


def _extract_published_at(soup: BeautifulSoup) -> datetime | None:
    for value in (
        _meta_content(soup, property_name="article:published_time"),
        _meta_content(soup, name="date"),
        _time_datetime(soup),
    ):
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _extract_text(html: str, soup: BeautifulSoup) -> str:
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
    )
    if extracted and extracted.strip():
        return extracted

    article = soup.find("article")
    if article is not None:
        article_text = article.get_text(" ", strip=True)
        if article_text:
            return article_text

    paragraphs = [
        paragraph.get_text(" ", strip=True)
        for paragraph in soup.find_all("p")
        if paragraph.get_text(strip=True)
    ]
    return " ".join(paragraphs)


def _extract_links(url: str, soup: BeautifulSoup) -> list[str]:
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        resolved = urljoin(url, anchor["href"])
        if resolved.startswith(("http://", "https://")) and resolved not in links:
            links.append(resolved)
    return links


def _meta_content(
    soup: BeautifulSoup,
    name: str | None = None,
    property_name: str | None = None,
) -> str | None:
    attrs = {"name": name} if name is not None else {"property": property_name}
    tag = soup.find("meta", attrs=attrs)
    if tag is None:
        return None
    content = tag.get("content")
    return content.strip() if isinstance(content, str) and content.strip() else None


def _json_ld_author(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        author = _author_from_json_ld(data)
        if author:
            return author
    return None


def _author_from_json_ld(data: Any) -> str | None:
    if isinstance(data, list):
        for item in data:
            if _is_article_json_ld(item):
                author = _author_from_json_ld(item)
                if author:
                    return author
        for item in data:
            author = _author_from_json_ld(item)
            if author:
                return author
        return None
    if not isinstance(data, dict):
        return None

    graph = data.get("@graph")
    if isinstance(graph, list):
        author = _author_from_json_ld(graph)
        if author:
            return author

    author = data.get("author")
    if isinstance(author, str):
        return author.strip() or None
    if isinstance(author, dict):
        name = author.get("name")
        return name.strip() if isinstance(name, str) and name.strip() else None
    if isinstance(author, list):
        for item in author:
            if isinstance(item, str) and item.strip():
                return item.strip()
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
    return None


def _is_article_json_ld(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    json_ld_type = data.get("@type")
    if isinstance(json_ld_type, str):
        return json_ld_type in {"Article", "NewsArticle"}
    if isinstance(json_ld_type, list):
        return any(item in {"Article", "NewsArticle"} for item in json_ld_type)
    return False


def _time_datetime(soup: BeautifulSoup) -> str | None:
    tag = soup.find("time")
    if tag is None:
        return None
    value = tag.get("datetime")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


class ArticleExtractor:
    """Compatibility wrapper around extract_article_from_html."""

    def extract(self, url: str, html: str) -> Article:
        return extract_article_from_html(url, html)
